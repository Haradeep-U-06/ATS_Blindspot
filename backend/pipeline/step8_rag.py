from typing import Any, Dict

from logger import get_logger
from rag.chunker import chunk_text
from rag.embedder import encode_texts
from rag.faiss_store import FaissJobStore
from rag.retriever import retrieve_relevant_chunks

logger = get_logger(__name__)


async def run_rag_pipeline(
    *,
    resume_id: str,
    job_id: str,
    jd_text: str,
    candidate_embedding: Any,
    store: FaissJobStore | None = None,
) -> Dict[str, Any]:
    logger.info("[STEP 8] Running RAG pipeline...")
    faiss_store = store or FaissJobStore(job_id)
    chunks = chunk_text(jd_text, source_type="job", source_id=job_id)
    logger.info("[INFO] Chunking JD | job_id=%s | chunks=%s", job_id, len(chunks))
    already_indexed = any(
        item.get("metadata", {}).get("source_type") == "job"
        and item.get("metadata", {}).get("source_id") == job_id
        for item in faiss_store.metadata
    )
    if chunks and not already_indexed:
        logger.info("[INFO] Adding chunks to FAISS index")
        embeddings = encode_texts([chunk["text"] for chunk in chunks])
        faiss_store.add(chunks, embeddings)
    elif already_indexed:
        logger.info("[INFO] JD chunks already indexed | job_id=%s", job_id)

    retrieved = retrieve_relevant_chunks(
        job_id=job_id,
        candidate_embedding=candidate_embedding,
        store=faiss_store,
    )
    logger.debug("[DEBUG] RAG retrieval complete | resume_id=%s | chunks=%s", resume_id, len(retrieved["chunks"]))
    return retrieved
