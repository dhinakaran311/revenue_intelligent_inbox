#!/usr/bin/env python3
"""seed_analyses.py — Seed prepared analyses into the database.

Reads all vetted JSON files from analysis/prepared/ and inserts them into
the analyses table with analysis_source='prepared'.
Updates record_processing_state.analysis_state = 'current' for each record.

Safe to run multiple times: checks if an identical (source_type, source_id,
source_revision, analysis_source='prepared') entry already exists.

Usage:
    python scripts/seed_analyses.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Add backend directory to sys.path so app imports work
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.analysis_contract import AnalysisOutput
from app.config import get_supabase_client
from app.services.analysis_service import persist_prepared_analysis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_analyses")


def seed_all() -> dict[str, int]:
    prepared_dir = ROOT_DIR / "analysis" / "prepared"
    if not prepared_dir.exists():
        logger.error("Prepared analysis directory not found: %s", prepared_dir)
        sys.exit(1)

    json_files = sorted(prepared_dir.glob("*.json"))
    if not json_files:
        logger.warning("No JSON files found in %s", prepared_dir)
        return {"total": 0, "inserted": 0, "skipped": 0, "errors": 0}

    logger.info("Found %d prepared analysis files to process", len(json_files))
    client = get_supabase_client()

    inserted = 0
    skipped = 0
    errors = 0

    for fpath in json_files:
        try:
            raw_text = fpath.read_text(encoding="utf-8")
            data = json.loads(raw_text)

            # Validate against Pydantic schema
            validated = AnalysisOutput.model_validate(data)
            val_dict = validated.model_dump()

            source_type = val_dict["source_type"]
            source_id = val_dict["source_id"]
            source_rev = val_dict["source_revision"]

            # Check if this exact analysis is already present
            existing = client.table("analyses").select("id").eq(
                "source_type", source_type
            ).eq("source_id", source_id).eq(
                "source_revision", source_rev
            ).eq("analysis_source", "prepared").execute()

            if existing.data:
                logger.info("Skipping %s (%s/%s rev %d): already seeded", fpath.name, source_type, source_id, source_rev)
                skipped += 1
                continue

            # Persist and update processing state
            persist_prepared_analysis(val_dict)
            logger.info("Seeded %s (%s/%s rev %d)", fpath.name, source_type, source_id, source_rev)
            inserted += 1

        except Exception as exc:
            logger.error("Error processing %s: %s", fpath.name, exc)
            errors += 1

    summary = {
        "total": len(json_files),
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors,
    }
    logger.info("Seeding complete: %s", summary)
    return summary


if __name__ == "__main__":
    res = seed_all()
    if res["errors"] > 0:
        sys.exit(1)
    sys.exit(0)
