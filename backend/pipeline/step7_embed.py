import json
from typing import Any, Dict, List

from rag.chunker import chunk_text
from rag.embedder import encode_texts, vector_to_b64
from rag.faiss_store import FaissResumeStore
from logger import get_logger

logger = get_logger(__name__)


def _json_text(value: Any) -> str:
    if not value:
        return ""
    return json.dumps(value, ensure_ascii=False, default=str)


def _candidate_sections(raw_text: str, candidate_profile: Dict[str, Any]) -> List[Dict[str, str]]:
    sections = [
        {"source_type": "resume_raw", "text": raw_text or ""},
        {"source_type": "resume_summary", "text": candidate_profile.get("summary", "")},
        {"source_type": "resume_skills", "text": _json_text(candidate_profile.get("skills", []))},
        {"source_type": "work_experience", "text": _json_text(candidate_profile.get("experience", []))},
        {"source_type": "projects", "text": _json_text(candidate_profile.get("projects", []))},
        {"source_type": "github", "text": _json_text(candidate_profile.get("github_data", {}))},
        {"source_type": "leetcode", "text": _json_text(candidate_profile.get("leetcode_data", {}))},
        {"source_type": "codeforces", "text": _json_text(candidate_profile.get("codeforces_data", {}))},
        {"source_type": "codechef", "text": _json_text(candidate_profile.get("codechef_data", {}))},
    ]
    return [section for section in sections if section["text"].strip()]


def build_candidate_chunks(
    *,
    resume_id: str,
    job_id: str,
    raw_text: str,
    candidate_profile: Dict[str, Any],
) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    for section in _candidate_sections(raw_text, candidate_profile):
        section_chunks = chunk_text(
            section["text"],
            source_type=section["source_type"],
            source_id=resume_id,
            extra_metadata={
                "resume_id": resume_id,
                "job_id": job_id,
                "section": section["source_type"],
            },
        )
        chunks.extend(section_chunks)

    for index, chunk in enumerate(chunks):
        chunk["chunk_id"] = f"{resume_id}_chunk_{index}"
        chunk["metadata"]["chunk_id"] = chunk["chunk_id"]
        chunk["metadata"]["chunk_index"] = index
    return chunks


async def vectorize_candidate_profile(
    *,
    db: Any,
    resume_id: str,
    job_id: str,
    raw_text: str,
    candidate_profile: Dict[str, Any],
    store: FaissResumeStore | None = None,
) -> Dict[str, Any]:
    logger.info("[STEP 7] Creating resume/external chunks | resume_id=%s", resume_id)
    chunks = build_candidate_chunks(
        resume_id=resume_id,
        job_id=job_id,
        raw_text=raw_text,
        candidate_profile=candidate_profile,
    )
    logger.info("[SUCCESS] %s chunks created | resume_id=%s", len(chunks), resume_id)
    if not chunks:
        raise ValueError("No chunks could be created for resume")

    logger.info("[STEP] Generating embeddings | resume_id=%s", resume_id)
    embeddings = encode_texts([chunk["text"] for chunk in chunks])
    logger.info("[SUCCESS] Embeddings generated | resume_id=%s | count=%s", resume_id, len(embeddings))

    faiss_store = store or FaissResumeStore(resume_id)
    faiss_store.clear()
    logger.info("[STEP] Storing chunks in per-resume FAISS namespace | resume_id=%s", resume_id)
    faiss_store.add(chunks, embeddings)

    if hasattr(db, "resume_chunks"):
        if hasattr(db.resume_chunks, "delete_many"):
            await db.resume_chunks.delete_many({"resume_id": resume_id})
        for chunk, embedding in zip(chunks, embeddings):
            document = {
                "chunk_id": chunk["chunk_id"],
                "resume_id": resume_id,
                "job_id": job_id,
                "text": chunk["text"],
                "metadata": chunk["metadata"],
                "embedding_b64": vector_to_b64(embedding),
                "faiss_namespace": faiss_store.namespace,
            }
            await db.resume_chunks.update_one(
                {"chunk_id": chunk["chunk_id"]},
                {"$set": document},
                upsert=True,
            )
    logger.info("[SUCCESS] Stored in FAISS | resume_id=%s | namespace=%s", resume_id, faiss_store.namespace)
    return {
        "chunk_count": len(chunks),
        "faiss_namespace": faiss_store.namespace,
        "chunks": chunks,
    }
