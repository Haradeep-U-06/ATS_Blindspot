"""
LLM-powered qualitative analysis for the candidate dashboard.

Generates: summary, strengths, weaknesses, skill_scores, evidence_commentary.
The overall numeric score is NEVER touched here — that stays math-only.
"""
import json
import re
from typing import Any, Dict, List, Optional

from logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_INSIGHTS_PROMPT = """You are a senior technical recruiter AI with expertise in software engineering roles.
You are given RAG-retrieved evidence chunks from a candidate's resume. Analyze them carefully.

JOB TITLE: {job_title}
REQUIRED SKILLS: {required_skills}

RESUME EVIDENCE CHUNKS (top {chunk_count} most relevant, ordered by relevance):
{chunks_text}

CANDIDATE'S VERIFIED SKILLS: {strengths}

Your task: Produce a precise, factual analysis based STRICTLY on what is written in the chunks above.
Do NOT hallucinate or assume anything not present in the text.

Respond ONLY with a valid JSON object in this exact schema:
{{
  "summary": "<3-4 sentence precise professional overview. Cover: (1) experience level and background, (2) specific technologies and frameworks they have worked with, (3) notable projects or achievements mentioned, (4) what role or domain they are best suited for. Be specific and factual — no filler phrases.>",
  "strengths": ["<specific verifiable strength from evidence — quote exact skills or projects mentioned>", "<strength 2>", "<strength 3>"],
  "weaknesses": [],
  "skill_scores": [
    {{"skill": "<exact skill name from required list>", "score": <0-100 integer>, "reason": "<quote specific evidence from chunks or state Not mentioned in resume>"}}
  ],
  "evidence_commentary": [
    {{"chunk_index": <0-based int>, "commentary": "<one precise sentence: what skills this chunk proves and why it is relevant to the job>"}}
  ]
}}

Scoring rules:
- 85-95: skill explicitly named AND demonstrated in a project or role (max is 95, never 100)
- 60-84: skill mentioned but without depth or project context
- 20-59: related concept mentioned indirectly
- 0-19: no evidence at all
- IMPORTANT: Do NOT assign 100 to any skill — cap all scores at 95
- skill_scores must list EVERY skill from the required list
- No markdown, no explanation outside JSON
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Optional[Dict]:
    """Try multiple strategies to extract a valid JSON object from LLM response."""
    text = text.strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to extract the first JSON block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass

    return None


def _build_chunks_text(top_chunks: List[Dict]) -> str:
    lines = []
    for i, chunk in enumerate(top_chunks):
        text = chunk.get("text", "").strip() if isinstance(chunk, dict) else str(chunk).strip()
        sim = chunk.get("similarity", 0) if isinstance(chunk, dict) else 0
        lines.append(f"[Chunk {i+1} | similarity={sim:.2f}]\n{text}")
    return "\n\n".join(lines) if lines else "No evidence chunks available."


def _safe_skill_list(required_skills: List[Any]) -> List[str]:
    result = []
    for s in required_skills:
        if isinstance(s, dict):
            result.append(s.get("skill", ""))
        elif isinstance(s, str):
            result.append(s)
    return [s for s in result if s]


def _fallback_insights(
    required_skills: List[str],
    strengths: List[str],
    top_chunks: List[Dict],
) -> Dict[str, Any]:
    """Return a deterministic (no-LLM) fallback if the LLM call fails."""
    strength_set = {s.lower() for s in strengths}
    skill_scores = []
    weaknesses = []
    for skill in required_skills:
        if skill.lower() in strength_set:
            skill_scores.append({"skill": skill, "score": 80, "reason": "Skill verified in resume."})
        else:
            skill_scores.append({"skill": skill, "score": 10, "reason": "No direct evidence found."})
            weaknesses.append(skill)

    return {
        "summary": "Resume analysis is available in text view.",
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "skill_scores": skill_scores,
        "evidence_commentary": [
            {"chunk_index": i, "commentary": "See raw text for details."}
            for i in range(len(top_chunks))
        ],
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def generate_dashboard_insights(
    *,
    job: Dict[str, Any],
    candidate: Dict[str, Any],
    score: Dict[str, Any],
    llm: Any,
) -> Dict[str, Any]:
    """
    Use the LLM to generate qualitative dashboard insights from RAG evidence chunks.
    Falls back to deterministic data if the LLM is unavailable.

    The overall numeric score is NOT modified here.
    """
    # ── Collect evidence chunks ──────────────────────────────────────────────
    evidence = score.get("evidence_chunks") or {}
    detail = score.get("subscores_detail") or {}
    top_chunks: List[Dict] = (
        evidence.get("top_chunks")
        or detail.get("top_chunks")
        or []
    )
    top_chunks = top_chunks[:10]  # retrieve up to 10 chunks for richer context

    required_skills = _safe_skill_list(job.get("required_skills", []))
    strengths: List[str] = score.get("strengths", [])
    job_title: str = job.get("title") or job.get("job_title") or "Software Engineer"

    if not top_chunks:
        logger.warning("[INSIGHTS] No RAG chunks available — using fallback")
        return _fallback_insights(required_skills, strengths, [])

    # ── Build prompt ─────────────────────────────────────────────────────────
    chunks_text = _build_chunks_text(top_chunks)
    prompt = _INSIGHTS_PROMPT.format(
        job_title=job_title,
        required_skills=", ".join(required_skills) if required_skills else "Not specified",
        chunk_count=len(top_chunks),
        chunks_text=chunks_text,
        strengths=", ".join(strengths) if strengths else "None verified",
    )

    # ── Call LLM ─────────────────────────────────────────────────────────────
    try:
        raw_response = await llm.generate(
            prompt,
            task="dashboard_insights",
            temperature=0.0,
        )
        parsed = _extract_json(raw_response)
        if not parsed:
            raise ValueError(f"LLM returned non-JSON: {raw_response[:200]}")

        # Normalise and validate essential keys
        insights = {
            "summary": str(parsed.get("summary") or ""),
            "strengths": parsed.get("strengths") or strengths[:5],
            "weaknesses": parsed.get("weaknesses") or [],
            "skill_scores": parsed.get("skill_scores") or [],
            "evidence_commentary": parsed.get("evidence_commentary") or [],
        }

        # Ensure skill_scores covers ALL required skills, and clamp max score to 95
        covered = {s["skill"].lower() for s in insights["skill_scores"] if isinstance(s, dict)}
        for skill in required_skills:
            if skill.lower() not in covered:
                in_strength = skill.lower() in {s.lower() for s in strengths}
                insights["skill_scores"].append({
                    "skill": skill,
                    "score": 70 if in_strength else 10,
                    "reason": "Verified in resume." if in_strength else "No direct evidence found.",
                })
        # Hard clamp: LLM must never give 100
        for s in insights["skill_scores"]:
            if isinstance(s, dict) and isinstance(s.get("score"), (int, float)):
                s["score"] = min(int(s["score"]), 95)

        logger.info("[INSIGHTS] LLM insights generated | chunks=%d skills=%d", len(top_chunks), len(insights["skill_scores"]))
        return insights

    except Exception as exc:
        logger.warning("[INSIGHTS] LLM failed — using fallback | error=%s", exc)
        return _fallback_insights(required_skills, strengths, top_chunks)
