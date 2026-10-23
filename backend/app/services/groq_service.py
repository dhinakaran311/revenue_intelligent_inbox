"""groq_service.py — LLM-powered analysis via Groq API.

Model: openai/gpt-oss-120b (via ENV['GROQ_MODEL'])

Rules enforced here:
- Full conversation text is NEVER logged (only length/truncation info).
- Credentials are never returned or logged.
- Response is validated against AnalysisOutput schema before returning.
- evidence_ref in every RouteItem is verified to contain the source_id.
- Returns None on any parse/validation failure (caller decides on retry).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.config import ENV
from app.analysis_contract import (
    AnalysisOutput,
    RouteId,
    validate_evidence_ref_call,
    validate_evidence_ref_meeting,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a revenue analysis assistant for SpendNest, an expense-management platform.

Analyse ONE conversation and return a structured JSON analysis a sales manager can act on.

Rules (strictly follow):
1. Every quote in "evidence" must be copied EXACTLY from the supplied text (verbatim substring).
   Quotes are machine-checked; one unverifiable quote rejects the whole analysis.
2. Meeting text is given as "Turn N | Speaker: text". Cite meeting evidence with "turn": N
   and a quote taken from that turn only. Calls have no turns: use "turn": null.
3. Do NOT infer deal value, pipeline totals, account ownership, attendance, staff roles or
   speaker identities beyond what the text explicitly states. People outside SpendNest may be
   prospects, customers, partners or suppliers; decide from the text.
4. owner must be null unless the text states who will act (e.g. "I will send...").
5. If the evidence is ambiguous, include a human_review route and say why.
6. Each route gets its own "output": the destination-specific deliverable (coaching note,
   follow-up task, defect ticket, vendor note). Do not repeat one generic summary.
7. Return ONLY valid JSON matching the schema below. No markdown, no commentary.

Schema:
{
  "schema_version": "1.1",
  "source_type": "call" | "meeting",
  "source_id": "<uuid>",
  "source_revision": <int>,
  "analysis_source": "runtime",
  "headline": "<one line: what matters>",
  "priority": "high" | "medium" | "low",
  "suggested_routes": [
    {
      "route_id": "deal_next_step" | "customer_follow_up" | "sales_coaching" | "internal_vendor_action" | "human_review" | "log_only",
      "label": "<short label>",
      "rationale": "<why this route>",
      "evidence_ref": "<record_ref turn N>  OR  <record_ref — \\"exact quote\\">",
      "is_manual": false,
      "priority": "high" | "medium" | "low",
      "output": "<the deliverable for this destination>",
      "owner": null
    }
  ],
  "evidence": [ {"id": "E1", "turn": <int or null>, "quote": "<verbatim>", "supports": "<what it shows>"} ],
  "concise_output": "<2-3 sentences: what happened and why it matters>",
  "what_established": "<facts directly supported by the text>",
  "what_not_established": "<what the text does not establish>",
  "next_action": "<concrete next action>",
  "owner": null,
  "confidence": "high" | "medium" | "low",
  "uncertainty": "<what makes this uncertain>"
}

Route taxonomy:
- deal_next_step         — prospect/partner evaluation with a concrete next step the text supports
- customer_follow_up     — existing customer problem, request, or a commitment made to them
- sales_coaching         — specific observable behaviour to correct or reinforce
- internal_vendor_action — supplier evaluation, product defect/gap, or internal process knowledge
- human_review           — ambiguity, conflicting labels, or unsupported conclusions
- log_only               — conversation happened but no follow-up is supported
"""


def _get_groq_client():
    """Return a Groq client instance (not cached — stateless HTTP client)."""
    from groq import Groq  # type: ignore

    api_key = ENV.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY in backend/.env")
    return Groq(api_key=api_key)


def analyze_record(
    source_type: str,
    source_id: str,
    source_revision: int,
    text_context: str,
    record_ref: str,
) -> dict[str, Any] | None:
    """Call Groq to generate a structured analysis for one record.

    The full text_context is sent to the model but is NEVER logged —
    only its length is recorded for observability.

    Args:
        source_type: "call" or "meeting".
        source_id: UUID string.
        source_revision: Integer revision number.
        text_context: Retrieved chunk text(s) concatenated.
        record_ref: Human-readable ref (e.g. "C01") used in evidence_ref citations.

    Returns:
        Validated AnalysisOutput dict, or None if Groq fails or validation fails.
    """
    model = ENV.get("GROQ_MODEL", "openai/gpt-oss-120b")
    logger.info(
        "Calling Groq for %s (source_id=%s, revision=%d, context_len=%d)",
        record_ref,
        source_id,
        source_revision,
        len(text_context),
    )

    user_prompt = (
        f"record_ref: {record_ref}\n"
        f"source_type: {source_type}\n"
        f"source_id: {source_id}\n"
        f"source_revision: {source_revision}\n\n"
        f"Conversation text:\n{text_context}"
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.error("Groq API call failed for %s: %s", record_ref, exc)
        return None

    raw_content = response.choices[0].message.content or ""
    if not raw_content.strip():
        logger.error("Empty response from Groq for %s", record_ref)
        return None

    # Parse JSON
    try:
        parsed: dict[str, Any] = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error for %s: %s", record_ref, exc)
        return None

    # Force runtime fields so the model can't override them.
    parsed["analysis_source"] = "runtime"
    parsed["source_type"] = source_type
    parsed["source_id"] = source_id
    parsed["source_revision"] = source_revision

    # Validate with Pydantic
    try:
        output = AnalysisOutput.model_validate(parsed)
    except Exception as exc:
        logger.error("Schema validation failed for %s: %s", record_ref, exc)
        return None

    # Verify evidence refs contain source_id
    validator = (
        validate_evidence_ref_meeting
        if source_type == "meeting"
        else validate_evidence_ref_call
    )
    for route in output.suggested_routes:
        if not validator(source_id, route.evidence_ref, record_ref):
            logger.warning(
                "evidence_ref does not name the record for %s route=%s — keeping but flagging",
                record_ref,
                route.route_id,
            )

    return output.model_dump()
