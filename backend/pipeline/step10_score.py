from typing import Any, Dict

from db.models import ScoreResult
from scoring.engine import ScoreEngine


async def score_candidate(
    *,
    candidate_profile: Dict[str, Any],
    job: Dict[str, Any],
    all_chunks: list[Dict[str, Any]] | None = None,
    engine: ScoreEngine | None = None,
) -> ScoreResult:
    return (engine or ScoreEngine()).compute(
        candidate_profile=candidate_profile, 
        jd_structured=job, 
        evaluation_result={}, 
        all_chunks=all_chunks
    )
