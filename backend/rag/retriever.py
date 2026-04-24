from typing import Any, Dict, List

import numpy as np

from config import settings
from logger import get_logger
from rag.faiss_store import FaissJobStore

logger = get_logger(__name__)


def retrieve_relevant_chunks(
    *,
    job_id: str,
    candidate_embedding: np.ndarray,
    top_k: int | None = None,
    max_chars: int = 1500,
    store: FaissJobStore | None = None,
) -> Dict[str, Any]:
    logger.info("[INFO] Retrieving top-%s chunks for candidate | job_id=%s", top_k or settings.rag_top_k, job_id)
    faiss_store = store or FaissJobStore(job_id)
    chunks: List[Dict[str, Any]] = faiss_store.search(candidate_embedding, k=top_k or settings.rag_top_k)
    context_parts = []
    used = 0
    for chunk in chunks:
        text = chunk.get("text", "")
        if used + len(text) > max_chars:
            text = text[: max(0, max_chars - used)]
        if text:
            context_parts.append(text)
            used += len(text)
        if used >= max_chars:
            break
    top_similarity = chunks[0]["similarity"] if chunks else 0.0
    logger.info("[SUCCESS] Retrieved %s relevant chunks | top_similarity=%.3f", len(chunks), top_similarity)
    if chunks:
        logger.debug("[DEBUG] Chunk[0] preview: %r", chunks[0].get("text", "")[:80])
    return {"chunks": chunks, "context": "\n\n".join(context_parts)}
