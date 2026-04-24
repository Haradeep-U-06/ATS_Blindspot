import json

import pytest

from db.models import ResumeStatus
from pipeline.orchestrator import run_job_evaluation, run_upload_vectorization_pipeline
from pipeline.step1_ingest import ingest_resume
from pipeline.step2_parse import extract_text_from_pdf
from pipeline.step3_structure import structure_resume
from pipeline.step6_process_jd import create_job_record, process_job_description
from pipeline.step7_embed import vectorize_candidate_profile
from pipeline.step8_rag import run_rag_for_resume
from pipeline.step9_evaluate import evaluate_candidate
from pipeline.step10_score import score_candidate
from pipeline.step11_store import persist_vectorized_candidate
from pipeline.step12_rank import rank_candidates
from rag.faiss_store import FaissResumeStore


class FakeUpload:
    filename = "resume.pdf"
    content_type = "application/pdf"

    async def read(self):
        return (
            b"Jane Doe\njane@example.com\nSkills: Python FastAPI MongoDB\n"
            b"Projects\nBuilt a FastAPI backend in Python with MongoDB.\n"
            b"Experience\nBuilt production APIs using Python and FastAPI.\n"
        )


class FakeRouter:
    async def generate(self, prompt: str, **kwargs):
        if "Job Description" in prompt:
            return json.dumps(
                {
                    "title": "Backend Engineer",
                    "required_skills": [{"skill": "Python", "weight": 0.6}, {"skill": "FastAPI", "weight": 0.4}],
                    "preferred_skills": [{"skill": "Docker", "weight": 1.0}],
                    "experience_years_min": 2,
                    "domain": "Backend",
                    "tech_vs_nontechnical_ratio": 1.0,
                    "key_responsibilities": ["Build APIs"],
                }
            )
        return json.dumps(
            {
                "overall_match_summary": "Candidate has explicit Python and FastAPI evidence.",
                "skill_matches": [
                    {
                        "skill": "Python",
                        "candidate_has": True,
                        "confidence": 0.95,
                        "notes": "Python appears in work/project chunks.",
                        "evidence": [{"source": "work_experience", "text": "Python APIs"}],
                        "evidence_sources": ["work_experience", "projects"],
                    },
                    {
                        "skill": "FastAPI",
                        "candidate_has": True,
                        "confidence": 0.9,
                        "notes": "FastAPI appears in project chunks.",
                        "evidence": [{"source": "projects", "text": "FastAPI backend"}],
                        "evidence_sources": ["projects"],
                    },
                    {
                        "skill": "Docker",
                        "candidate_has": False,
                        "confidence": 0.0,
                        "notes": "No Docker evidence.",
                        "evidence": [],
                        "evidence_sources": [],
                    },
                ],
                "experience_match": {"years_required": 2, "years_candidate": 0, "match_score": 0.8},
                "strengths": ["Python", "FastAPI"],
                "gaps": ["Docker"],
                "recommendation": "strong_fit",
                "confidence": 0.9,
            }
        )


class BrokenRouter:
    async def generate(self, prompt: str, **kwargs):
        from llm.exceptions import LLMUnavailableError

        raise LLMUnavailableError("providers unavailable")


class NoFitRouter:
    async def generate(self, prompt: str, **kwargs):
        return json.dumps(
            {
                "overall_match_summary": "No matching technical evidence found.",
                "skill_matches": [
                    {"skill": "Python", "candidate_has": False, "confidence": 0.0, "evidence": [], "evidence_sources": []},
                    {"skill": "FastAPI", "candidate_has": False, "confidence": 0.0, "evidence": [], "evidence_sources": []},
                    {"skill": "REST API", "candidate_has": False, "confidence": 0.0, "evidence": [], "evidence_sources": []},
                ],
                "experience_match": {"years_required": 2, "years_candidate": 0, "match_score": 0.0},
                "strengths": [],
                "gaps": ["Python", "FastAPI", "REST API"],
                "recommendation": "no_fit",
                "confidence": 0.5,
            }
        )


@pytest.mark.asyncio
async def test_upload_processing_vectorizes_without_scoring(mock_db, monkeypatch, tmp_path, caplog):
    monkeypatch.setattr("config.settings.faiss_index_dir", str(tmp_path))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_github_profile", lambda username: async_value({"username": username, "languages": ["Python"]}))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_leetcode_profile", lambda username: async_value({}))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_codeforces_profile", lambda username: async_value({}))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_codechef_profile", lambda username: async_value({}))

    job = await create_job_record(jd_text="Need Python FastAPI backend engineer.", db=mock_db)
    ingest = await ingest_resume(FakeUpload(), mock_db)
    await mock_db.resumes.update_one({"resume_id": ingest["resume_id"]}, {"$set": {"job_id": job["job_id"]}})

    await run_upload_vectorization_pipeline(
        ingest["resume_id"],
        job["job_id"],
        ingest["raw_bytes"],
        ingest["filename"],
        {"github": "https://github.com/jane"},
        mock_db,
    )

    resume = await mock_db.resumes.find_one({"resume_id": ingest["resume_id"]})
    candidate = await mock_db.candidates.find_one({"resume_id": ingest["resume_id"]})

    assert resume["status"] == ResumeStatus.ready_for_evaluation.value
    assert resume["chunk_count"] > 0
    assert candidate["github_username"] == "jane"
    assert await mock_db.scores.count_documents({}) == 0
    assert "Waiting for evaluation trigger" in caplog.text


@pytest.mark.asyncio
async def test_resume_structuring_uses_no_llm_and_does_not_extract_links_from_resume():
    class ExplodingRouter:
        async def generate(self, *args, **kwargs):
            raise AssertionError("resume parsing must not call LLM")

    structured = await structure_resume(
        resume_id="resume_test",
        raw_text=(
            "Jane Doe\n"
            "jane@example.com\n"
            "GitHub: should_not_be_used\n"
            "Skills: Python FastAPI MongoDB Docker REST APIs\n"
            "Project: Built a backend API."
        ),
        external_links={"github": "https://github.com/provided-user"},
        llm_router=ExplodingRouter(),
    )

    assert structured["name"] == "Jane Doe"
    assert structured["email"] == "jane@example.com"
    assert any(skill["skill"] == "Python" for skill in structured["skills"])
    assert structured["github_username"] == "provided-user"


@pytest.mark.asyncio
async def test_evaluation_trigger_scores_ready_resumes(mock_db, monkeypatch, tmp_path):
    monkeypatch.setattr("config.settings.faiss_index_dir", str(tmp_path))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_github_profile", lambda username: async_value({"username": username, "languages": ["Python"]}))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_leetcode_profile", lambda username: async_value({}))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_codeforces_profile", lambda username: async_value({}))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_codechef_profile", lambda username: async_value({}))

    job = await create_job_record(jd_text="Need Python FastAPI backend engineer with Docker.", db=mock_db)
    ingest = await ingest_resume(FakeUpload(), mock_db)
    await mock_db.resumes.update_one({"resume_id": ingest["resume_id"]}, {"$set": {"job_id": job["job_id"]}})
    await run_upload_vectorization_pipeline(
        ingest["resume_id"],
        job["job_id"],
        ingest["raw_bytes"],
        ingest["filename"],
        {"github": "jane"},
        mock_db,
    )

    result = await run_job_evaluation(job_id=job["job_id"], db=mock_db, llm_router=FakeRouter())
    ranking = await rank_candidates(db=mock_db, job_id=job["job_id"])

    assert result["status"] == "completed"
    assert ranking["total"] == 1
    assert ranking["candidates"][0]["final_score"] > 70
    job_after = await mock_db.jobs.find_one({"job_id": job["job_id"]})
    assert job_after["application_window_closed"] is True
    assert job_after["evaluation_status"] == "completed"


@pytest.mark.asyncio
async def test_evaluation_recovers_resumes_left_in_evaluating(mock_db, monkeypatch, tmp_path):
    monkeypatch.setattr("config.settings.faiss_index_dir", str(tmp_path))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_github_profile", lambda username: async_value({"username": username, "languages": ["Python"]}))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_leetcode_profile", lambda username: async_value({}))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_codeforces_profile", lambda username: async_value({}))
    monkeypatch.setattr("pipeline.step4_enrich.fetch_codechef_profile", lambda username: async_value({}))

    job = await create_job_record(jd_text="Need Python FastAPI backend engineer with Docker.", db=mock_db)
    ingests = [await ingest_resume(FakeUpload(), mock_db), await ingest_resume(FakeUpload(), mock_db)]
    for ingest in ingests:
        await mock_db.resumes.update_one({"resume_id": ingest["resume_id"]}, {"$set": {"job_id": job["job_id"]}})
        await run_upload_vectorization_pipeline(
            ingest["resume_id"],
            job["job_id"],
            ingest["raw_bytes"],
            ingest["filename"],
            {"github": "jane"},
            mock_db,
        )
    await mock_db.resumes.update_one({"resume_id": ingests[0]["resume_id"]}, {"$set": {"status": ResumeStatus.evaluating.value}})

    result = await run_job_evaluation(job_id=job["job_id"], db=mock_db, llm_router=FakeRouter())
    ranking = await rank_candidates(db=mock_db, job_id=job["job_id"])

    assert result["status"] == "completed"
    assert result["scored"] == 2
    assert ranking["total"] == 2
    assert await mock_db.resumes.count_documents({"job_id": job["job_id"], "status": ResumeStatus.completed.value}) == 2


@pytest.mark.asyncio
async def test_jd_processing_uses_fallback_when_llm_is_unavailable(mock_db):
    job = await process_job_description(
        jd_text="We need a Backend Engineer with 3+ years experience. Required: Python, FastAPI, MongoDB, REST APIs. Preferred: Docker, CI/CD.",
        db=mock_db,
        llm_router=BrokenRouter(),
    )

    assert job["title"] == "Backend Engineer"
    assert job["experience_years_min"] == 3
    required_skills = {item["skill"] for item in job["required_skills"]}
    preferred_skills = {item["skill"] for item in job["preferred_skills"]}
    assert "Python" in required_skills
    assert "FastAPI" in required_skills
    assert "Docker" in preferred_skills
    assert "CI/CD" in preferred_skills
    assert await mock_db.jobs.count_documents({}) == 1


@pytest.mark.asyncio
async def test_evaluation_uses_evidence_only_fallback_when_llm_is_unavailable(tmp_path):
    job = {
        "job_id": "job_test",
        "required_skills": [{"skill": "Python", "weight": 0.6}, {"skill": "FastAPI", "weight": 0.4}],
        "preferred_skills": [{"skill": "Docker", "weight": 1.0}],
        "experience_years_min": 2,
    }
    chunks = [
        {
            "text": "Built a Python FastAPI project.",
            "metadata": {"source_type": "projects", "source_id": "resume_test", "chunk_id": "c1"},
        }
    ]
    store = FaissResumeStore("resume_test", index_dir=str(tmp_path))
    from rag.embedder import encode_texts

    store.add(chunks, encode_texts([chunk["text"] for chunk in chunks]))
    rag = await run_rag_for_resume(resume_id="resume_test", job=job, store=store)
    evaluation = await evaluate_candidate(
        resume_id="resume_test",
        candidate_profile={},
        job=job,
        rag_context=rag["context"],
        rag_evidence=rag,
        llm_router=BrokenRouter(),
    )

    assert evaluation["recommendation"] == "strong_fit"
    assert evaluation["skill_matches"][0]["candidate_has"] is True
    assert any(match["skill"] == "Docker" and not match["candidate_has"] for match in evaluation["skill_matches"])


@pytest.mark.asyncio
async def test_evaluation_uses_structured_resume_skills_when_rag_misses_exact_chunks():
    job = {
        "job_id": "job_test",
        "required_skills": [
            {"skill": "Python", "weight": 0.25},
            {"skill": "FastAPI", "weight": 0.25},
            {"skill": "MongoDB", "weight": 0.25},
            {"skill": "REST APIs", "weight": 0.25},
        ],
        "preferred_skills": [
            {"skill": "Docker", "weight": 1 / 3},
            {"skill": "AWS", "weight": 1 / 3},
            {"skill": "CI/CD", "weight": 1 / 3},
        ],
        "experience_years_min": 3,
    }
    candidate_profile = {
        "skills": [
            {"skill": "Python", "source": "resume_explicit", "confidence": 1.0},
            {"skill": "FastAPI", "source": "resume_explicit", "confidence": 1.0},
            {"skill": "MongoDB", "source": "resume_explicit", "confidence": 1.0},
            {"skill": "REST APIs", "source": "resume_explicit", "confidence": 1.0},
            {"skill": "AWS", "source": "resume_explicit", "confidence": 1.0},
            {"skill": "CI/CD", "source": "resume_explicit", "confidence": 1.0},
        ],
    }

    evaluation = await evaluate_candidate(
        resume_id="resume_test",
        candidate_profile=candidate_profile,
        job=job,
        rag_context="",
        rag_evidence={"evidence_by_skill": {}, "context": "", "chunks": []},
        llm_router=BrokenRouter(),
    )
    score = await score_candidate(candidate_profile=candidate_profile, job=job, evaluation=evaluation)

    by_skill = {match["skill"]: match for match in evaluation["skill_matches"]}
    assert by_skill["Python"]["candidate_has"] is True
    assert by_skill["FastAPI"]["candidate_has"] is True
    assert by_skill["MongoDB"]["candidate_has"] is True
    assert by_skill["REST APIs"]["candidate_has"] is True
    assert by_skill["Docker"]["candidate_has"] is False
    assert by_skill["AWS"]["candidate_has"] is True
    assert by_skill["CI/CD"]["candidate_has"] is True
    assert evaluation["recommendation"] == "strong_fit"
    assert score.final_score > 70


@pytest.mark.asyncio
async def test_evaluation_overrides_llm_no_fit_with_validated_resume_skills():
    job = {
        "job_id": "job_test",
        "required_skills": [{"skill": "Python", "weight": 0.5}, {"skill": "FastAPI", "weight": 0.5}],
        "preferred_skills": [{"skill": "REST API", "weight": 1.0}],
        "experience_years_min": 2,
    }
    candidate_profile = {
        "skills": [
            {"skill": "Python", "source": "resume_explicit", "confidence": 1.0},
            {"skill": "FastAPI", "source": "resume_explicit", "confidence": 1.0},
            {"skill": "REST APIs", "source": "resume_explicit", "confidence": 1.0},
        ],
    }

    evaluation = await evaluate_candidate(
        resume_id="resume_test",
        candidate_profile=candidate_profile,
        job=job,
        rag_context="",
        rag_evidence={"evidence_by_skill": {}, "context": "", "chunks": []},
        llm_router=NoFitRouter(),
    )
    score = await score_candidate(candidate_profile=candidate_profile, job=job, evaluation=evaluation)
    skill_scores = {item["skill"]: item for item in score.subscores_detail["skill_scores"]}

    assert evaluation["recommendation"] == "strong_fit"
    assert all(match["candidate_has"] for match in evaluation["skill_matches"])
    assert score.final_score > 70
    assert skill_scores["Python"]["score"] > 0
    assert skill_scores["FastAPI"]["score"] > 0
    assert skill_scores["REST API"]["score"] > 0


@pytest.mark.asyncio
async def test_manual_vectorize_and_persist_path(mock_db, tmp_path):
    raw_text = "Jane Doe\nSkills: Python FastAPI\nProjects\nBuilt FastAPI backend in Python."
    structured = await structure_resume(resume_id="resume_manual", raw_text=raw_text, external_links={})
    vectorized = await vectorize_candidate_profile(
        db=mock_db,
        resume_id="resume_manual",
        job_id="job_manual",
        raw_text=raw_text,
        candidate_profile=structured,
        store=FaissResumeStore("resume_manual", index_dir=str(tmp_path)),
    )
    await mock_db.resumes.insert_one({"resume_id": "resume_manual", "filename": "resume.pdf", "status": "uploaded"})
    persisted = await persist_vectorized_candidate(
        db=mock_db,
        resume_id="resume_manual",
        job_id="job_manual",
        raw_text=raw_text,
        candidate_profile=structured,
        chunk_count=vectorized["chunk_count"],
    )

    assert persisted["chunk_count"] > 0
    assert await mock_db.resume_chunks.count_documents({"resume_id": "resume_manual"}) == vectorized["chunk_count"]


@pytest.mark.asyncio
async def test_pdf_parser_text_decode_fallback():
    raw_text = await extract_text_from_pdf(resume_id="resume_test", raw_pdf_bytes=b"Jane Doe Python FastAPI" * 10)

    assert "Jane Doe" in raw_text


async def async_value(value):
    return value
