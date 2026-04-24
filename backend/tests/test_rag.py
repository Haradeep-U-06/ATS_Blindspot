import numpy as np

from rag.chunker import chunk_text
from rag.embedder import encode_texts
from rag.faiss_store import FaissJobStore
from rag.retriever import retrieve_relevant_chunks


def test_chunker_output_contains_metadata():
    text = "Python FastAPI MongoDB. " * 80
    chunks = chunk_text(text, source_type="job", source_id="job_test", chunk_size=128, chunk_overlap=16)

    assert chunks
    assert chunks[0]["metadata"]["source_type"] == "job"
    assert chunks[0]["metadata"]["source_id"] == "job_test"
    assert len(chunks[0]["text"]) <= 128


def test_faiss_store_add_query_round_trip(tmp_path):
    chunks = [
        {"text": "python fastapi backend", "metadata": {"source_type": "job", "source_id": "job1", "chunk_index": 0}},
        {"text": "react frontend design", "metadata": {"source_type": "job", "source_id": "job1", "chunk_index": 1}},
    ]
    vectors = encode_texts([chunk["text"] for chunk in chunks])
    store = FaissJobStore("job1", index_dir=str(tmp_path))
    store.add(chunks, vectors)

    results = store.search(encode_texts(["python backend"])[0], k=1)

    assert len(results) == 1
    assert "python" in results[0]["text"]


def test_retriever_returns_context(tmp_path):
    chunks = [
        {"text": "must have python api experience", "metadata": {"source_type": "job", "source_id": "job2", "chunk_index": 0}},
        {"text": "nice to have figma", "metadata": {"source_type": "job", "source_id": "job2", "chunk_index": 1}},
    ]
    store = FaissJobStore("job2", index_dir=str(tmp_path))
    store.add(chunks, encode_texts([chunk["text"] for chunk in chunks]))

    result = retrieve_relevant_chunks(job_id="job2", candidate_embedding=np.asarray(encode_texts(["python api"])[0]), store=store, top_k=2)

    assert len(result["chunks"]) == 2
    assert result["context"]
