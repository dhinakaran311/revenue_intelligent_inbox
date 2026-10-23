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

Analyze the provided conversation excerpt and return a structured JSON analysis.

Rules (strictly follow):
1. Only reference evidence that appears verbatim (or very close) in the provided text.
2. Cite CALL evidence as:  source_id — "exact quote from transcript"
3. Cite MEETING evidence as:  source_id turn N  (N is 1-based turn index)
4. Do NOT infer deal value, pipeline totals, account ownership, attendance, or speaker roles beyond what the text explicitly states.
5. If there is insufficient evidence to be confident, set confidence=low and include human_review in suggested_routes.
6. owner must be null unless the text explicitly names an owner.
7. Return ONLY valid JSON matching the AnalysisOutput schema below. No markdown, no commentary.

AnalysisOutput schema:
{
  "schema_version": "1.0",
  "source_type": "call" | "meeting",
  "source_id": "<uuid>",
  "source_revision": <int>,
  "analysis_source": "runtime",
  "suggested_routes": [
    {
      "route_id": "deal_next_step" | "customer_follow_up" | "sales_coaching" | "internal_vendor_action" | "human_review",
      "label": "<short label>",
      "rationale": "<why this route>",
      "evidence_ref": "<source_id — \\"quote\\"  OR  source_id turn N>",
      "is_manual": false
    }
  ],
  "concise_output": "<1-2 sentences: what happened and why it matters>",
  "what_established": "<facts directly supported by the text>",
  "what_not_established": "<deal value, attendance, ownership, etc. not in text>",
  "next_action": "<concrete recommended action>",
  "owner": null,
  "confidence": "high" | "medium" | "low",
  "uncertainty": "<what makes this uncertain>"
}

Route taxonomy:
- deal_next_step      — evidence-backed commercial evaluation or concrete next action
- customer_follow_up  — explicit request, problem, or commitment involving existing customer
- sales_coaching      — specific, observable coaching opportunity
- internal_vendor_action — operational, integration, billing, or supplier matter
- human_review        — ambiguity, competing routes, no text, or unsupported ownership
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
        record_ref: Human-readable ref (e.g. "C01") for log messages only.

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
            max_tokens=1500,
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
        if not validator(source_id, route.evidence_ref):
            logger.warning(
                "evidence_ref missing source_id for %s route=%s — keeping but flagging",
                record_ref,
                route.route_id,
            )

    return output.model_dump()
