import pytest

from rag.chunker import chunk_text
from rag.embedder import encode_texts
from rag.faiss_store import FaissJobStore, FaissResumeStore
from pipeline.step8_rag import run_rag_for_resume


def test_chunker_output_contains_metadata():
    text = "Python FastAPI MongoDB. " * 80
    chunks = chunk_text(
        text,
        source_type="resume_raw",
        source_id="resume_test",
        extra_metadata={"job_id": "job_test"},
        chunk_size=128,
        chunk_overlap=16,
    )

    assert chunks
    assert chunks[0]["metadata"]["source_type"] == "resume_raw"
    assert chunks[0]["metadata"]["source_id"] == "resume_test"
    assert chunks[0]["metadata"]["job_id"] == "job_test"
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


@pytest.mark.asyncio
async def test_per_resume_rag_returns_context(tmp_path):
    chunks = [
        {"text": "candidate built python api experience", "metadata": {"source_type": "projects", "source_id": "resume2", "chunk_index": 0}},
        {"text": "candidate used figma", "metadata": {"source_type": "resume_raw", "source_id": "resume2", "chunk_index": 1}},
    ]
    store = FaissResumeStore("resume2", index_dir=str(tmp_path))
    store.add(chunks, encode_texts([chunk["text"] for chunk in chunks]))

    result = await run_rag_for_resume(
        resume_id="resume2",
        job={"job_id": "job2", "required_skills": [{"skill": "Python", "weight": 1.0}], "preferred_skills": []},
        store=store,
        top_k=2,
    )

    assert "Python" in result["evidence_by_skill"]
    assert result["context"]
