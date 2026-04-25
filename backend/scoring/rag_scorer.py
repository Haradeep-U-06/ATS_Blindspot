"""
Deterministic chunk-level RAG scorer.

NO LLM involved. Everything is pure math:
  chunk_score = 0.6 × skill_match + 0.4 × semantic_similarity

Then:
  RAG_SCORE   = mean(top-3 chunk scores)
  FINAL_SCORE = ATS_WEIGHT × ATS_SCORE + RAG_WEIGHT × RAG_SCORE

  where ATS_WEIGHT / RAG_WEIGHT are dynamically chosen based on ATS_SCORE.

All operations on the same data → same result (fully deterministic).
"""

import re
from typing import Any, Dict, List, Tuple

from logger import get_logger

logger = get_logger(__name__)

# ── constants ────────────────────────────────────────────────────────────────
SIMILARITY_THRESHOLD   = 0.70   # keep chunks above this
MIN_STRONG_CHUNKS      = 5      # fallback if not enough pass threshold
CHUNK_SKILL_WEIGHT     = 0.60
CHUNK_SEMANTIC_WEIGHT  = 0.40
TOP_EVIDENCE_COUNT     = 5

# Dynamic ATS/RAG blending thresholds
HIGH_ATS   = 85.0
LOW_ATS    = 60.0
W_ATS_HIGH = (0.80, 0.20)
W_ATS_MID  = (0.70, 0.30)
W_ATS_LOW  = (0.50, 0.50)


# ── helpers ───────────────────────────────────────────────────────────────────

def _skill_re(skill: str) -> re.Pattern:
    """Compile a word-boundary regex for a skill (cached per call)."""
    return re.compile(rf"\b{re.escape(skill.lower())}\b", flags=re.IGNORECASE)


def _skill_match_score(chunk_text: str, jd_skills: Dict[str, float]) -> Tuple[float, bool]:
    """
    Fraction of JD skills explicitly present in the chunk text.
    Returns (match_score, has_core_keyword).
    """
    if not jd_skills:
        return 0.0, False
    hits = 0
    has_core = False
    for skill, weight in jd_skills.items():
        if _skill_re(skill).search(chunk_text):
            hits += 1
            if weight >= 1.5:
                has_core = True
    return hits / len(jd_skills), has_core


def _infer_chunk_type(metadata: Dict[str, Any]) -> str:
    """
    Derive chunk_type from existing source_type metadata without changing the
    stored schema — maps source_type → one of: skill / project / experience / external.
    """
    src = str(metadata.get("source_type") or metadata.get("type") or "").lower()
    if src in {"resume_skills"}:
        return "skill"
    if src in {"projects"}:
        return "project"
    if src in {"work_experience"}:
        return "experience"
    if src in {"github", "leetcode", "codeforces", "codechef"}:
        return "external"
    return "general"


def _score_chunk(
    chunk: Dict[str, Any],
    jd_skills: Dict[str, float],
) -> float:
    """
    Deterministic score for a single retrieved chunk.

    chunk_score = 0.6 × skill_match + 0.4 × semantic_similarity
    Keyword Boost: if core keyword present -> score * 1.5
    """
    text      = chunk.get("text", "") or ""
    sim       = float(chunk.get("similarity", 0.0) or 0.0)  # cosine score from FAISS
    skill_hit, has_core = _skill_match_score(text, jd_skills)
    
    score     = CHUNK_SKILL_WEIGHT * skill_hit + CHUNK_SEMANTIC_WEIGHT * sim
    if has_core:
        score *= 1.5
        
    return round(min(1.0, max(0.0, score)), 6)


def _filter_chunks(
    chunks: List[Dict[str, Any]],
    jd_skills: Dict[str, float],
) -> Tuple[List[Dict[str, Any]], List[float]]:
    """
    1. Score all chunks.
    2. Apply similarity threshold (>= SIMILARITY_THRESHOLD).
    3. Fallback to top-MIN_STRONG_CHUNKS if fewer than MIN_STRONG_CHUNKS pass.
    Returns (selected_chunks, scores_parallel).
    """
    # Score every chunk
    scored = [
        (chunk, _score_chunk(chunk, jd_skills))
        for chunk in chunks
    ]
    # Sort descending by chunk score
    scored.sort(key=lambda x: x[1], reverse=True)

    # Apply similarity threshold
    strong = [(c, s) for c, s in scored if float(c.get("similarity", 0.0)) >= SIMILARITY_THRESHOLD]

    # Fallback if not enough strong chunks
    if len(strong) < MIN_STRONG_CHUNKS:
        strong = scored[:MIN_STRONG_CHUNKS]

    return [c for c, _ in strong], [s for _, s in strong]


def compute_rag_score(
    all_chunks: List[Dict[str, Any]],
    jd_skills: Dict[str, float],
) -> Dict[str, Any]:
    """
    Pure deterministic RAG scoring — no LLM.

    Returns:
        rag_score       – 0-100 float
        keyword_score   – 0-100 float
        matched_keywords - list of keywords found in top chunks
        top_chunks      – top-3 evidence chunks (enriched with chunk_type + chunk_score)
        chunk_scores    – score per top chunk
        avg_similarity  – average similarity of top chunks
        strong_count    – how many chunks passed the threshold
    """
    if not all_chunks:
        return {
            "rag_score":      0.0,
            "keyword_score":  0.0,
            "matched_keywords": [],
            "top_chunks":     [],
            "chunk_scores":   [],
            "avg_similarity": 0.0,
            "strong_count":   0,
        }

    selected, scores = _filter_chunks(all_chunks, jd_skills)

    # Take only top-3 for RAG score
    top_chunks = selected[:TOP_EVIDENCE_COUNT]
    top_scores = scores[:TOP_EVIDENCE_COUNT]

    # Keyword Evidence Scoring
    # Extract keywords from the top 3 chunks
    combined_text = " ".join([c.get("text", "") or "" for c in top_chunks])
    
    matched_keywords = []
    keyword_score_num = 0.0
    keyword_score_den = 0.0
    
    for skill, weight in jd_skills.items():
        keyword_score_den += weight
        # Check if skill is in combined top chunks text
        if _skill_re(skill).search(combined_text):
            matched_keywords.append(skill)
            # Exact match gives 1.0 match score
            keyword_score_num += (weight * 1.0)
            
    keyword_score_raw = (keyword_score_num / keyword_score_den) if keyword_score_den > 0 else 0.0

    # Enrich chunks with derived metadata (non-destructive)
    enriched = []
    for chunk, score in zip(top_chunks, top_scores):
        ec = dict(chunk)
        meta = dict(ec.get("metadata") or {})
        meta["chunk_type"]  = _infer_chunk_type(meta)
        meta["chunk_score"] = round(score, 4)
        ec["metadata"]      = meta
        ec["chunk_score"]   = round(score, 4)
        enriched.append(ec)

    rag_score_raw    = (sum(top_scores) / len(top_scores)) if top_scores else 0.0
    avg_sim          = sum(float(c.get("similarity", 0)) for c in top_chunks) / max(1, len(top_chunks))

    logger.info(
        "[RAG_SCORER] rag_score=%.3f | keyword_score=%.3f | top_chunks=%d | avg_sim=%.3f | strong=%d",
        rag_score_raw, keyword_score_raw, len(top_chunks), avg_sim, len(selected),
    )

    return {
        "rag_score":      round(rag_score_raw * 100.0, 2),   # 0-100
        "keyword_score":  round(keyword_score_raw * 100.0, 2), # 0-100
        "matched_keywords": matched_keywords,
        "top_chunks":     enriched,
        "chunk_scores":   [round(s, 4) for s in top_scores],
        "avg_similarity": round(avg_sim, 4),
        "strong_count":   len(selected),
    }


# Dynamic ATS/RAG/KEYWORD blending thresholds
HIGH_ATS   = 85.0
LOW_ATS    = 60.0
W_ATS_HIGH = (0.75, 0.15, 0.10)
W_ATS_MID  = (0.60, 0.25, 0.15)
W_ATS_LOW  = (0.50, 0.30, 0.20)


def blend_scores(
    ats_score:  float,
    rag_score:  float,
    keyword_score: float,
    avg_similarity: float,
    strong_count:   int,
) -> Dict[str, Any]:
    """
    Combine ATS, RAG, and Keyword scores with dynamic weights.
    Also produces a confidence metric.

    Returns:
        final_score       – 0-100 float
        ats_weight        – used
        rag_weight        – used
        keyword_weight    – used
        confidence_score  – 0-1 float
    """
    # Dynamic weight selection
    if ats_score > HIGH_ATS:
        ats_w, rag_w, key_w = W_ATS_HIGH
    elif ats_score < LOW_ATS:
        ats_w, rag_w, key_w = W_ATS_LOW
    else:
        ats_w, rag_w, key_w = W_ATS_MID

    final = ats_w * ats_score + rag_w * rag_score + key_w * keyword_score
    final = round(min(100.0, max(0.0, final)), 2)

    # Confidence: blend of average similarity, evidence count, and ATS/RAG agreement
    sim_conf     = min(1.0, avg_similarity)
    evidence_conf = min(1.0, strong_count / TOP_EVIDENCE_COUNT)
    agreement     = 1.0 - abs(ats_score - rag_score) / 100.0
    confidence    = round((0.4 * sim_conf + 0.3 * evidence_conf + 0.3 * agreement), 4)

    logger.info(
        "[BLEND] ats=%.1f (w=%.2f) rag=%.1f (w=%.2f) key=%.1f (w=%.2f) → final=%.2f | conf=%.3f",
        ats_score, ats_w, rag_score, rag_w, keyword_score, key_w, final, confidence,
    )

    return {
        "final_score":      final,
        "ats_weight":       ats_w,
        "rag_weight":       rag_w,
        "keyword_weight":   key_w,
        "confidence_score": confidence,
    }
