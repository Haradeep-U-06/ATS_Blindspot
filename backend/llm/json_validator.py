import json
import re
from typing import Any, Awaitable, Callable, Optional

from llm.exceptions import JSONRepairError
from llm.prompts import JSON_REPAIR_PROMPT
from logger import get_logger

logger = get_logger(__name__)

RepairCallback = Callable[[str], Awaitable[str]]


def _strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_first_json_block(text: str) -> Optional[str]:
    stripped = text.strip()
    candidates = []
    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    if object_start != -1 and object_end != -1 and object_end > object_start:
        candidates.append((object_start, stripped[object_start : object_end + 1]))
    array_start = stripped.find("[")
    array_end = stripped.rfind("]")
    if array_start != -1 and array_end != -1 and array_end > array_start:
        candidates.append((array_start, stripped[array_start : array_end + 1]))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def _loads(text: str) -> Any:
    return json.loads(text)


async def parse_json_response(
    response_text: str,
    *,
    repair_callback: Optional[RepairCallback] = None,
    resume_id: Optional[str] = None,
) -> Any:
    attempts = [response_text, _strip_markdown_fences(response_text)]
    extracted = _extract_first_json_block(response_text)
    if extracted:
        attempts.append(extracted)

    last_error: Exception | None = None
    for candidate in attempts:
        try:
            return _loads(candidate)
        except Exception as exc:
            last_error = exc

    logger.error(
        "[ERROR] JSON parsing failed | resume_id=%s | error=%s",
        resume_id or "n/a",
        last_error,
    )
    logger.debug("[DEBUG] Broken JSON response | response=%s", response_text)

    if repair_callback is not None:
        logger.info("[INFO] Attempting JSON repair...")
        try:
            repaired = await repair_callback(JSON_REPAIR_PROMPT.format(broken_json=response_text))
            for candidate in (repaired, _strip_markdown_fences(repaired), _extract_first_json_block(repaired) or ""):
                if not candidate:
                    continue
                try:
                    return _loads(candidate)
                except Exception as exc:
                    last_error = exc
        except Exception as exc:
            last_error = exc

    logger.error("[ERROR] Repair failed — marking resume as parse_failed")
    raise JSONRepairError(str(last_error))
