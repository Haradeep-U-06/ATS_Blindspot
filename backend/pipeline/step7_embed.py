from typing import Any, Dict

import numpy as np

from logger import get_logger
from rag.embedder import encode_texts, vector_to_b64

logger = get_logger(__name__)


def candidate_text(candidate_profile: Dict[str, Any]) -> str:
    skills = [item.get("skill", item) if isinstance(item, dict) else item for item in candidate_profile.get("skills", [])]
    experience = " ".join(item.get("description", "") for item in candidate_profile.get("experience", []) if isinstance(item, dict))
    projects = " ".join(item.get("description", "") for item in candidate_profile.get("projects", []) if isinstance(item, dict))
    return " ".join(
        [
            candidate_profile.get("name", ""),
            candidate_profile.get("summary", ""),
            " ".join(map(str, skills)),
            experience,
            projects,
        ]
    ).strip()


def jd_text(job: Dict[str, Any]) -> str:
    required = " ".join(item.get("skill", "") for item in job.get("required_skills", []))
    preferred = " ".join(item.get("skill", "") for item in job.get("preferred_skills", []))
    responsibilities = " ".join(job.get("key_responsibilities", []))
    return " ".join([job.get("title", ""), job.get("domain", ""), required, preferred, responsibilities, job.get("raw_jd_text", "")]).strip()


async def generate_embeddings(
    *,
    resume_id: str,
    candidate_profile: Dict[str, Any],
    job: Dict[str, Any],
) -> Dict[str, Any]:
    logger.info("[STEP 7] Generating embeddings...")
    c_text = candidate_text(candidate_profile)
    j_text = jd_text(job)
    logger.debug("[DEBUG] Candidate text length: %s chars", len(c_text))
    logger.info("[INFO] Encoding candidate vector...")
    vectors = encode_texts([c_text, j_text])
    candidate_embedding = np.asarray(vectors[0], dtype=np.float32)
    jd_embedding = np.asarray(vectors[1], dtype=np.float32)
    logger.info("[SUCCESS] Candidate embedding created | dim=%s | resume_id=%s", candidate_embedding.shape[0], resume_id)
    logger.info("[INFO] Encoding JD vector...")
    logger.info("[SUCCESS] JD embedding created | dim=%s | job_id=%s", jd_embedding.shape[0], job.get("job_id"))
    return {
        "candidate_text": c_text,
        "jd_text": j_text,
        "candidate_embedding": candidate_embedding,
        "jd_embedding": jd_embedding,
        "candidate_embedding_b64": vector_to_b64(candidate_embedding),
        "jd_embedding_b64": vector_to_b64(jd_embedding),
    }
