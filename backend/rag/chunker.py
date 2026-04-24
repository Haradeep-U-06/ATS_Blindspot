from typing import Any, Dict, List

from logger import get_logger

logger = get_logger(__name__)


def chunk_text(
    text: str,
    *,
    source_type: str,
    source_id: str,
    extra_metadata: Dict[str, Any] | None = None,
    chunk_size: int = 256,
    chunk_overlap: int = 32,
) -> List[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return []

    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        parts = splitter.split_text(text)
    except Exception:
        parts = []
        start = 0
        step = max(1, chunk_size - chunk_overlap)
        while start < len(text):
            parts.append(text[start : start + chunk_size])
            start += step

    chunks = [
        {
            "text": part,
            "metadata": {
                "source_type": source_type,
                "source_id": source_id,
                "chunk_index": index,
                **(extra_metadata or {}),
            },
        }
        for index, part in enumerate(parts)
        if part.strip()
    ]
    logger.debug(
        "[DEBUG] Chunked text | source_type=%s | source_id=%s | chunks=%s",
        source_type,
        source_id,
        len(chunks),
    )
    return chunks
