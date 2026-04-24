from typing import Any

from config import settings
from logger import get_logger

logger = get_logger(__name__)

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except Exception:  # pragma: no cover - dependency is provided in production
    AsyncIOMotorClient = None


_client: Any = None
_db: Any = None


async def connect_to_mongo() -> None:
    global _client, _db
    if _db is not None:
        return
    if AsyncIOMotorClient is None:
        logger.warning("[WARN] Motor is not installed; MongoDB connection unavailable")
        return
    logger.info("[INFO] Connecting to MongoDB | db=%s", settings.mongodb_db_name)
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client[settings.mongodb_db_name]
    logger.info("[SUCCESS] MongoDB client initialized | db=%s", settings.mongodb_db_name)


async def close_mongo_connection() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
    logger.info("[INFO] MongoDB connection closed")


def get_database() -> Any:
    if _db is None:
        raise RuntimeError("MongoDB is not initialized. Call connect_to_mongo() first.")
    return _db


def set_database_for_tests(database: Any) -> None:
    global _db
    _db = database
