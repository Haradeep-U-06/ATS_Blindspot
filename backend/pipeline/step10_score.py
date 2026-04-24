from typing import Any, Dict

from db.models import ScoreResult
from scoring.engine import ScoreEngine


async def score_candidate(
    *,
    candidate_profile: Dict[str, Any],
    job: Dict[str, Any],
    evaluation: Dict[str, Any],
    engine: ScoreEngine | None = None,
) -> ScoreResult:
    return (engine or ScoreEngine()).compute(candidate_profile, job, evaluation)
