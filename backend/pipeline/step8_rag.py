from typing import Any, Dict, List

from config import settings
from rag.embedder import encode_texts
from rag.faiss_store import FaissResumeStore
from logger import get_logger

logger = get_logger(__name__)


def jd_tech_skills(job: Dict[str, Any]) -> List[Dict[str, Any]]:
    seen = set()
    skills: List[Dict[str, Any]] = []
    for requirement_type in ("required", "preferred"):
        for item in job.get(f"{requirement_type}_skills", []) or []:
            skill = str(item.get("skill", "")).strip()
            if not skill or skill.lower() in seen:
                continue
            seen.add(skill.lower())
            skills.append(
                {
                    "skill": skill,
                    "weight": float(item.get("weight", 0.0) or 0.0),
                    "requirement_type": requirement_type,
                }
            )
    return skills


async def run_rag_for_resume(
    *,
    resume_id: str,
    job: Dict[str, Any],
    top_k: int | None = None,
    store: FaissResumeStore | None = None,
) -> Dict[str, Any]:
    logger.info("[STEP 8] Running per-resume RAG | resume_id=%s | job_id=%s", resume_id, job.get("job_id"))
    faiss_store = store or FaissResumeStore(resume_id)
    skills = jd_tech_skills(job)
    if not skills:
        logger.warning("[WARN] No JD technical skills available for retrieval | resume_id=%s", resume_id)
        return {"evidence_by_skill": {}, "context": "", "chunks": []}

    evidence_by_skill: Dict[str, List[Dict[str, Any]]] = {}
    all_chunks: List[Dict[str, Any]] = []
    limit = top_k or settings.rag_top_k
    for item in skills:
        skill = item["skill"]
        query = f"Explicit evidence that the candidate used {skill} in resume, project, work experience, or external profile"
        query_vector = encode_texts([query])[0]
        chunks = faiss_store.search(query_vector, k=limit)
        evidence_by_skill[skill] = chunks
        all_chunks.extend(chunks)
        logger.info(
            "[SUCCESS] Retrieved %s chunks for %s | resume_id=%s",
            len(chunks),
            skill,
            resume_id,
        )

    context_parts = []
    for skill, chunks in evidence_by_skill.items():
        if not chunks:
            continue
        context_parts.append(f"Skill: {skill}")
        for chunk in chunks:
            source = (chunk.get("metadata") or {}).get("source_type", "unknown")
            context_parts.append(f"[{source}] {chunk.get('text', '')}")
    context = "\n\n".join(context_parts)
    logger.info("[SUCCESS] Per-resume RAG complete | resume_id=%s | skills=%s", resume_id, len(skills))
    return {
        "evidence_by_skill": evidence_by_skill,
        "context": context,
        "chunks": all_chunks,
    }
