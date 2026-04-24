import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from config import settings
from logger import get_logger
from rag.embedder import EMBEDDING_DIM

logger = get_logger(__name__)

try:
    import faiss
except Exception:  # pragma: no cover - production dependency
    faiss = None


def _normalize(vectors: np.ndarray) -> np.ndarray:
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


class FaissStore:
    def __init__(self, namespace: str, index_dir: str | None = None, dim: int = EMBEDDING_DIM) -> None:
        self.namespace = namespace
        self.dim = dim
        self.index_dir = Path(index_dir or settings.faiss_index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / f"{namespace}.index"
        self.metadata_path = self.index_dir / f"{namespace}.metadata.json"
        self.vectors_path = self.index_dir / f"{namespace}.vectors.npy"
        self.metadata: List[Dict[str, Any]] = []
        self.index = None
        self.vectors = np.empty((0, self.dim), dtype=np.float32)
        self.load()

    def load(self) -> None:
        if self.metadata_path.exists():
            self.metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        if faiss is not None and self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            logger.info("[INFO] FAISS index loaded | namespace=%s | vectors=%s", self.namespace, self.index.ntotal)
            return
        if self.vectors_path.exists():
            self.vectors = np.load(self.vectors_path).astype(np.float32)
            logger.info("[INFO] Fallback vector store loaded | namespace=%s | vectors=%s", self.namespace, len(self.vectors))

    def _ensure_index(self) -> None:
        if faiss is not None and self.index is None:
            self.index = faiss.IndexFlatIP(self.dim)

    def add(self, chunks: List[Dict[str, Any]], embeddings: np.ndarray) -> None:
        if not chunks:
            return
        vectors = _normalize(embeddings)
        if vectors.shape[1] != self.dim:
            raise ValueError(f"Expected embedding dim {self.dim}, got {vectors.shape[1]}")
        if len(chunks) != len(vectors):
            raise ValueError("chunks and embeddings length mismatch")

        self.metadata.extend(chunks)
        if faiss is not None:
            self._ensure_index()
            self.index.add(vectors)
        else:
            self.vectors = np.vstack([self.vectors, vectors])
        self.save()
        total = self.index.ntotal if self.index is not None else len(self.vectors)
        logger.info("[SUCCESS] FAISS index updated | namespace=%s | total_vectors=%s", self.namespace, total)

    def save(self) -> None:
        self.metadata_path.write_text(json.dumps(self.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        if faiss is not None and self.index is not None:
            faiss.write_index(self.index, str(self.index_path))
        else:
            np.save(self.vectors_path, self.vectors)

    def clear(self) -> None:
        self.metadata = []
        self.index = None
        self.vectors = np.empty((0, self.dim), dtype=np.float32)
        for path in (self.index_path, self.metadata_path, self.vectors_path):
            if path.exists():
                path.unlink()
        logger.info("[INFO] Cleared FAISS namespace | namespace=%s", self.namespace)

    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        if not self.metadata:
            return []
        query = _normalize(query_vector).astype(np.float32)
        k = min(k, len(self.metadata))
        if faiss is not None and self.index is not None and self.index.ntotal:
            scores, indices = self.index.search(query, k)
            pairs = zip(scores[0], indices[0])
        else:
            scores = self.vectors @ query.reshape(-1)
            top_indices = np.argsort(scores)[::-1][:k]
            pairs = [(scores[index], index) for index in top_indices]

        results = []
        for score, index in pairs:
            if index < 0 or index >= len(self.metadata):
                continue
            item = dict(self.metadata[index])
            item["similarity"] = float(score)
            results.append(item)
        return results


class FaissJobStore(FaissStore):
    def __init__(self, job_id: str, index_dir: str | None = None, dim: int = EMBEDDING_DIM) -> None:
        self.job_id = job_id
        super().__init__(f"job_{job_id}", index_dir=index_dir, dim=dim)


class FaissResumeStore(FaissStore):
    def __init__(self, resume_id: str, index_dir: str | None = None, dim: int = EMBEDDING_DIM) -> None:
        self.resume_id = resume_id
        super().__init__(f"resume_{resume_id}", index_dir=index_dir, dim=dim)
