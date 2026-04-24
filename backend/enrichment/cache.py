import time
from typing import Any, Optional


_CACHE: dict[str, tuple[float, Any]] = {}


def get_cached(key: str, ttl_seconds: int) -> Optional[Any]:
    item = _CACHE.get(key)
    if not item:
        return None
    stored_at, value = item
    if time.time() - stored_at > ttl_seconds:
        _CACHE.pop(key, None)
        return None
    return value


def set_cached(key: str, value: Any) -> None:
    _CACHE[key] = (time.time(), value)
