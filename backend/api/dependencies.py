from typing import Any

from fastapi import Header

from db.mongo import get_database


async def get_db() -> Any:
    return get_database()


async def get_hr_user_id(x_hr_user_id: str | None = Header(default=None)) -> str:
    return x_hr_user_id or "default_hr"


def serialize_mongo(value: Any) -> Any:
    if isinstance(value, list):
        return [serialize_mongo(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_mongo(item) for key, item in value.items() if key != "_id"}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
