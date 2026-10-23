#!/usr/bin/env python3
"""chunk_and_embed.py — Chunk, embed, and upsert usable conversation records to Pinecone.

Pipeline:
  1. Fetch all source_records from Supabase where has_usable_text=true.
  2. For M07 (or any record at revision > 1), clean up old revision vectors.
  3. Chunk each record using deterministic IDs: {source_type}_{source_id}_{revision}_chunk{n}.
  4. Embed chunks with sentence-transformers/all-MiniLM-L6-v2 (384 dimensions).
  5. Upsert chunks into Pinecone in batches.

Idempotent: stable chunk IDs mean re-running is safe.

Usage:
    python scripts/chunk_and_embed.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Add backend directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_supabase_client
from app.services.chunker import chunk_record
from app.services.embedder import embed_chunks
from app.services.pinecone_service import delete_old_revision_chunks, upsert_chunks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chunk_and_embed")


def run() -> dict[str, int]:
    client = get_supabase_client()

    logger.info("Fetching records with usable text from Supabase...")
    resp = client.table("source_records").select(
        "source_type, source_id, record_ref, revision, has_usable_text, source_payload, transcript_payload"
    ).eq("has_usable_text", True).execute()

    records = resp.data or []
    logger.info("Found %d records with usable text", len(records))

    all_chunks = []
    cleaned_count = 0

    for rec in records:
        s_type = rec["source_type"]
        s_id = rec["source_id"]
        rev = rec.get("revision", 1)
        ref = rec.get("record_ref") or s_id

        # If revision > 1, clean up vectors from previous revisions (e.g. M07 revision 1)
        if rev > 1:
            for old_rev in range(1, rev):
                del_res = delete_old_revision_chunks(s_type, s_id, old_rev)
                if del_res.get("deleted_count", 0) > 0:
                    logger.info("Deleted %d old rev-%d vectors for %s", del_res["deleted_count"], old_rev, ref)
                    cleaned_count += del_res["deleted_count"]

        # Chunk record
        chunks = chunk_record(rec)
        if chunks:
            logger.info("Generated %d chunk(s) for %s (%s/%s rev %d)", len(chunks), ref, s_type, s_id, rev)
            all_chunks.extend(chunks)
        else:
            logger.warning("No chunks generated for %s despite has_usable_text=true", ref)

    if not all_chunks:
        logger.warning("No chunks to embed or upsert")
        return {"records": len(records), "chunks": 0, "upserted": 0, "old_vectors_deleted": cleaned_count}

    logger.info("Embedding %d total chunks...", len(all_chunks))
    embedded_chunks = embed_chunks(all_chunks)

    logger.info("Upserting chunks to Pinecone...")
    upsert_res = upsert_chunks(embedded_chunks)
    upserted_count = upsert_res.get("upserted_count", 0)

    summary = {
        "records": len(records),
        "chunks": len(all_chunks),
        "upserted": upserted_count,
        "old_vectors_deleted": cleaned_count,
    }
    logger.info("Chunking and embedding complete: %s", summary)
    return summary


if __name__ == "__main__":
    res = run()
    sys.exit(0)
