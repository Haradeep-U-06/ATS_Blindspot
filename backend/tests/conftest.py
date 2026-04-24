import logging
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def capture_ats_logs(caplog):
    logger = logging.getLogger("ats")
    old_propagate = logger.propagate
    logger.propagate = True
    caplog.set_level(logging.DEBUG, logger="ats")
    yield
    logger.propagate = old_propagate


@pytest.fixture
async def mock_db():
    try:
        from mongomock_motor import AsyncMongoMockClient

        client = AsyncMongoMockClient()
        return client["ats_test"]
    except ModuleNotFoundError:
        return InMemoryAsyncDB()


@pytest.fixture(autouse=True)
def force_test_embedder(monkeypatch):
    from rag.embedder import get_embedder
    from config import settings

    get_embedder.cache_clear()
    monkeypatch.setattr(settings, "cloudinary_cloud_name", None)
    monkeypatch.setattr(settings, "cloudinary_api_key", None)
    monkeypatch.setattr(settings, "cloudinary_api_secret", None)

    def _load_model(self):
        self._fallback = True

    monkeypatch.setattr("rag.embedder.SentenceTransformerEmbedder._load_model", _load_model)
    yield
    get_embedder.cache_clear()


class InMemoryCursor:
    def __init__(self, documents):
        self.documents = list(documents)

    def sort(self, key, direction):
        reverse = direction < 0
        self.documents.sort(key=lambda doc: doc.get(key, 0), reverse=reverse)
        return self

    def skip(self, count):
        self.documents = self.documents[count:]
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    async def to_list(self, length=None):
        return self.documents if length is None else self.documents[:length]


class InMemoryCollection:
    def __init__(self):
        self.documents = []

    async def insert_one(self, document):
        self.documents.append(dict(document))
        return type("InsertOneResult", (), {"inserted_id": len(self.documents)})()

    async def find_one(self, query):
        for document in self.documents:
            if _matches(document, query):
                return dict(document)
        return None

    async def update_one(self, query, update, upsert=False):
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                changed = dict(document)
                changed.update(update.get("$set", {}))
                self.documents[index] = changed
                return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1})()
        if upsert:
            document = dict(query)
            document.update(update.get("$set", {}))
            self.documents.append(document)
        return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()

    async def count_documents(self, query):
        return sum(1 for document in self.documents if _matches(document, query))

    def find(self, query):
        return InMemoryCursor([dict(document) for document in self.documents if _matches(document, query)])


class InMemoryAsyncDB:
    def __init__(self):
        self.resumes = InMemoryCollection()
        self.candidates = InMemoryCollection()
        self.scores = InMemoryCollection()
        self.jobs = InMemoryCollection()


def _matches(document, query):
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif actual != expected:
            return False
    return True
