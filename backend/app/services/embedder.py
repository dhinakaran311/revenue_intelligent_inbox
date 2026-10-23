"""embedder.py — Sentence-Transformers embedding service.

Uses sentence-transformers/all-MiniLM-L6-v2 (384-dimensional output).
The model is loaded lazily on first call to avoid import-time overhead and
allow the module to be imported in environments where torch is not installed.

Never logs or stores raw texts beyond what the caller already holds.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer as _ST

_model: "_ST | None" = None
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _get_model() -> "_ST":
    """Return the singleton SentenceTransformer model, loading it if needed."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Encode a list of strings into 384-dim float embeddings.

    Args:
        texts: Non-empty list of strings to embed.

    Returns:
        List of 384-dim float vectors, one per input string.
    """
    if not texts:
        return []
    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return [vec.tolist() for vec in embeddings]


def embed_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add an 'embedding' key (384-dim list[float]) to each chunk dict in-place.

    Args:
        chunks: List of chunk dicts as returned by chunker.chunk_record.

    Returns:
        The same list with 'embedding' added to every dict.
    """
    if not chunks:
        return chunks

    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)

    for chunk, vec in zip(chunks, vectors):
        chunk["embedding"] = vec

    return chunks
