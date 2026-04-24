import base64
import hashlib
from functools import lru_cache
from typing import Iterable, List

import numpy as np

from logger import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 384


class SentenceTransformerEmbedder:
    def __init__(self) -> None:
        self._model = None
        self._fallback = False

    def _load_model(self) -> None:
        if self._model is not None or self._fallback:
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("[INFO] SentenceTransformer model loaded (singleton)")
        except Exception as exc:
            self._fallback = True
            logger.warning("[WARN] SentenceTransformer unavailable — using deterministic test embedder | error=%s", exc)

    def encode(self, texts: Iterable[str]) -> np.ndarray:
        self._load_model()
        text_list = list(texts)
        if not text_list:
            return np.empty((0, EMBEDDING_DIM), dtype=np.float32)
        if self._model is not None:
            vectors = self._model.encode(text_list, convert_to_numpy=True, batch_size=32)
            return np.asarray(vectors, dtype=np.float32)
        return np.vstack([_deterministic_vector(text) for text in text_list]).astype(np.float32)


def _deterministic_vector(text: str) -> np.ndarray:
    vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    tokens = (text or "").lower().split()
    for token in tokens or [text]:
        digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
        for offset in range(0, len(digest), 4):
            index = int.from_bytes(digest[offset : offset + 4], "big") % EMBEDDING_DIM
            vector[index] += 1.0
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformerEmbedder:
    return SentenceTransformerEmbedder()


def encode_texts(texts: List[str]) -> np.ndarray:
    return get_embedder().encode(texts)


def vector_to_b64(vector: np.ndarray) -> str:
    arr = np.asarray(vector, dtype=np.float32)
    return base64.b64encode(arr.tobytes()).decode("ascii")


def b64_to_vector(value: str) -> np.ndarray:
    raw = base64.b64decode(value.encode("ascii"))
    return np.frombuffer(raw, dtype=np.float32)
