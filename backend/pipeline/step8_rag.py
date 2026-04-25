from typing import Any, Dict, List

from config import settings
from rag.embedder import encode_texts
from rag.faiss_store import FaissResumeStore
from logger import get_logger

logger = get_logger(__name__)

# Retrieve more chunks per skill so the scorer has material to filter
RAG_RETRIEVE_K = 10
RAG_THRESHOLD  = 0.70


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
                    "skill":            skill,
                    "weight":           float(item.get("weight", 0.0) or 0.0),
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
        return {"evidence_by_skill": {}, "context": "", "chunks": [], "all_chunks": []}

    # Retrieve top-10 per skill (increased from default)
    limit = top_k or max(RAG_RETRIEVE_K, settings.rag_top_k)

    evidence_by_skill: Dict[str, List[Dict[str, Any]]] = {}
    all_chunks: List[Dict[str, Any]] = []

    for item in skills:
        skill = item["skill"]
        query = f"Explicit evidence that the candidate used {skill} in resume, project, work experience, or external profile"
        query_vector = encode_texts([query])[0]
        chunks = faiss_store.search(query_vector, k=limit)

        # Apply similarity threshold (strong chunks only; fallback handled in rag_scorer)
        strong = [c for c in chunks if float(c.get("similarity", 0.0)) >= RAG_THRESHOLD]
        # Always keep at least top-3 regardless of threshold
        if len(strong) < 3:
            strong = chunks[:3]

        evidence_by_skill[skill] = strong
        all_chunks.extend(strong)

        logger.info(
            "[SUCCESS] Retrieved %s chunks for %s (threshold≥%.2f kept %s) | resume_id=%s",
            len(chunks), skill, RAG_THRESHOLD, len(strong), resume_id,
        )

    # Build plain-text context for any LLM step that still needs it
    context_parts = []
    for skill, chunks in evidence_by_skill.items():
        if not chunks:
            continue
        context_parts.append(f"Skill: {skill}")
        for chunk in chunks:
            source = (chunk.get("metadata") or {}).get("source_type", "unknown")
            context_parts.append(f"[{source}] {chunk.get('text', '')}")
    context = "\n\n".join(context_parts)

    logger.info("[SUCCESS] Per-resume RAG complete | resume_id=%s | skills=%s | total_chunks=%s",
                resume_id, len(skills), len(all_chunks))

    return {
        "evidence_by_skill": evidence_by_skill,
        "context":           context,
        "chunks":            all_chunks,   # backward-compat key
        "all_chunks":        all_chunks,   # explicit alias
    }
