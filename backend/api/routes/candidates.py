from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_db, serialize_mongo

router = APIRouter(tags=["candidates"])


async def _candidate_payload(candidate_id: str, db: Any) -> dict:
    candidate = await db.candidates.find_one({"candidate_id": candidate_id})
    if not candidate:
        raise HTTPException(status_code=404, detail="candidate_id not found")
    scores = await db.scores.find({"candidate_id": candidate_id}).sort("created_at", -1).to_list(length=50)
    payload = {**candidate, "scores": scores}
    return serialize_mongo(payload)


@router.get("/candidate/{candidate_id}")
async def get_candidate_profile(candidate_id: str, db: Any = Depends(get_db)) -> dict:
    return await _candidate_payload(candidate_id, db)


@router.get("/candidates/{candidate_id}")
async def get_candidate_profile_hr(candidate_id: str, db: Any = Depends(get_db)) -> dict:
    return await _candidate_payload(candidate_id, db)
