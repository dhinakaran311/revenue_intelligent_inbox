"""pinecone_service.py — Pinecone vector store operations.

Index:     volopay-index (dim=384, cosine)
Namespace: from ENV['PINECONE_NAMESPACE'] (default: 'development')

Chunk IDs follow the stable pattern:
    {source_type}_{source_id}_{revision}_chunk{n}

Full conversation text is NEVER stored in metadata (Pinecone 40 KB limit).
Only lightweight metadata is stored: source_type, source_id, source_revision,
chunk_index, text_hash.

This module never logs credentials or raw embeddings.
"""
from __future__ import annotations

from typing import Any

from app.config import ENV

_pinecone_index = None


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------

def get_pinecone_index():
    """Return a Pinecone Index object, creating it on first call.

    Uses ENV['PINECONE_API_KEY'] and ENV['PINECONE_INDEX_NAME'].
    """
    global _pinecone_index
    if _pinecone_index is None:
        from pinecone import Pinecone  # pinecone v3+

        api_key = ENV.get("PINECONE_API_KEY", "")
        index_name = ENV.get("PINECONE_INDEX_NAME", "volopay-index")
        if not api_key:
            raise RuntimeError("Missing PINECONE_API_KEY in backend/.env")

        pc = Pinecone(api_key=api_key)
        _pinecone_index = pc.Index(index_name)
    return _pinecone_index


def _namespace() -> str:
    return ENV.get("PINECONE_NAMESPACE", "development")


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def upsert_chunks(chunks_with_embeddings: list[dict[str, Any]]) -> dict[str, int]:
    """Upsert chunks into Pinecone.

    Supports both Document schema indexes (via index.documents) and vector indexes (via index.upsert).

    Args:
        chunks_with_embeddings: List of chunk dicts.

    Returns:
        {'upserted_count': N}
    """
    if not chunks_with_embeddings:
        return {"upserted_count": 0}

    index = get_pinecone_index()
    ns = _namespace()

    if hasattr(index, "documents"):
        docs = []
        for chunk in chunks_with_embeddings:
            docs.append({
                "_id": chunk["chunk_id"],
                "chunk_text": chunk.get("text", ""),
                "title": f"{chunk['source_type']}_{chunk.get('record_ref', chunk['source_id'])}",
            })
        batch_size = 50
        total_upserted = 0
        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            resp = index.documents.upsert(namespace=ns, documents=batch)
            total_upserted += getattr(resp, "upserted_count", len(batch))
        return {"upserted_count": total_upserted}

    vectors = []
    for chunk in chunks_with_embeddings:
        metadata: dict[str, Any] = {
            "source_type": chunk["source_type"],
            "source_id": chunk["source_id"],
            "source_revision": chunk["source_revision"],
            "chunk_index": chunk["chunk_index"],
            "text_hash": chunk.get("text_hash", ""),
        }
        if "turn_start" in chunk:
            metadata["turn_start"] = chunk["turn_start"]
        if "turn_end" in chunk:
            metadata["turn_end"] = chunk["turn_end"]

        vectors.append(
            {
                "id": chunk["chunk_id"],
                "values": chunk["embedding"],
                "metadata": metadata,
            }
        )

    batch_size = 100
    total_upserted = 0
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i : i + batch_size]
        index.upsert(vectors=batch, namespace=ns)
        total_upserted += len(batch)

    return {"upserted_count": total_upserted}


# ---------------------------------------------------------------------------
# Delete old revision
# ---------------------------------------------------------------------------

def delete_old_revision_chunks(
    source_type: str,
    source_id: str,
    old_revision: int,
) -> dict[str, int]:
    """Delete all Pinecone vectors or documents from a superseded source revision."""
    index = get_pinecone_index()
    ns = _namespace()
    prefix = f"{source_type}_{source_id}_{old_revision}_chunk"

    if hasattr(index, "documents"):
        ids_to_delete: list[str] = []
        try:
            for page in index.documents.list(namespace=ns, prefix=prefix).pages():
                for item in getattr(page, "items", []):
                    doc_id = getattr(item, "id", None) or getattr(item, "_id", None)
                    if doc_id:
                        ids_to_delete.append(doc_id)
        except Exception:
            ids_to_delete = []

        if ids_to_delete:
            index.documents.delete(namespace=ns, ids=ids_to_delete)
        return {"deleted_count": len(ids_to_delete)}

    ids_to_delete = []
    try:
        for page in index.list(prefix=prefix, namespace=ns):
            ids_to_delete.extend(page)
    except Exception:
        ids_to_delete = []

    if not ids_to_delete:
        return {"deleted_count": 0}

    index.delete(ids=ids_to_delete, namespace=ns)
    return {"deleted_count": len(ids_to_delete)}


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def query_similar(
    source_type: str,
    source_id: str,
    query_text: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Query Pinecone for the most semantically relevant chunks for a record.

    For document-schema indexes, uses documents.search() with embed scoring.
    Falls back to prefix listing if semantic search is unavailable.

    Args:
        source_type: 'call' | 'meeting'
        source_id:   UUID of the record
        query_text:  The text to embed and search against
        top_k:       Max number of results

    Returns:
        List of {'chunk_id': str, 'score': float, 'chunk_text': str}
    """
    index = get_pinecone_index()
    ns = _namespace()

    if hasattr(index, "documents"):
        # Try semantic search first
        try:
            resp = index.documents.search(
                namespace=ns,
                top_k=top_k * 3,  # Fetch more then filter to this record
                score_by=[{"type": "embed", "field": "chunk_text", "query": query_text}],
                include_fields=["chunk_text"],
            )
            prefix = f"{source_type}_{source_id}"
            results = []
            hits = getattr(resp, "hits", None) or getattr(resp, "results", [])
            if isinstance(hits, dict):
                hits = hits.get("hits", [])
            for hit in hits:
                hit_id = getattr(hit, "_id", None) or getattr(hit, "id", None) or hit.get("_id", "")
                if hit_id.startswith(prefix):
                    text = (
                        getattr(hit, "chunk_text", None)
                        or (hit.get("fields", {}) or {}).get("chunk_text", "")
                    )
                    results.append({
                        "chunk_id": hit_id,
                        "score": getattr(hit, "_score", None) or hit.get("_score", 0.0),
                        "chunk_text": text,
                    })
                if len(results) >= top_k:
                    break
            if results:
                return results
        except Exception:
            pass  # Fall through to prefix listing

        # Fallback: prefix listing (returns all chunks for this record)
        try:
            prefix = f"{source_type}_{source_id}"
            results = []
            for page in index.documents.list(namespace=ns, prefix=prefix, limit=top_k).pages():
                for item in getattr(page, "items", []):
                    doc_id = getattr(item, "id", None) or getattr(item, "_id", None)
                    if doc_id:
                        chunk_text = getattr(item, "chunk_text", "") or ""
                        results.append({"chunk_id": doc_id, "score": 1.0, "chunk_text": chunk_text})
            return results
        except Exception:
            return []

    # Vector index path
    from app.services.embedder import embed_text
    embedding = embed_text(query_text)
    response = index.query(
        vector=embedding,
        top_k=top_k,
        namespace=ns,
        filter={"source_type": {"$eq": source_type}, "source_id": {"$eq": source_id}},
        include_metadata=True,
    )
    results = []
    for match in response.get("matches", []):
        results.append(
            {
                "chunk_id": match["id"],
                "score": match["score"],
                "chunk_text": match.get("metadata", {}).get("text_preview", ""),
            }
        )
    return results

