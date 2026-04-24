import json

import pytest

from db.models import ScoreResult
from pipeline.step1_ingest import ingest_resume
from pipeline.step2_parse import extract_text_from_pdf
from pipeline.step3_structure import structure_resume
from pipeline.step4_enrich import enrich_profile
from pipeline.step5_infer_skills import infer_skills
from pipeline.step6_process_jd import process_job_description
from pipeline.step7_embed import generate_embeddings
from pipeline.step8_rag import run_rag_pipeline
from pipeline.step9_evaluate import evaluate_candidate
from pipeline.step11_store import persist_results
from pipeline.step12_rank import rank_candidates
from rag.faiss_store import FaissJobStore


class FakeUpload:
    filename = "resume.pdf"
    content_type = "application/pdf"

    async def read(self):
        return b"Jane Doe Python FastAPI MongoDB GitHub jane" * 10


class FakeRouter:
    async def generate(self, prompt: str, **kwargs):
        if "Parse this Job Description" in prompt:
            return json.dumps(
                {
                    "title": "Backend Engineer",
                    "required_skills": [{"skill": "Python", "weight": 0.6}, {"skill": "FastAPI", "weight": 0.4}],
                    "preferred_skills": [{"skill": "Docker", "weight": 1.0}],
                    "experience_years_min": 2,
                    "domain": "Backend",
                    "tech_vs_nontechnical_ratio": 0.9,
                    "key_responsibilities": ["Build APIs"],
                }
            )
        if "infer additional technical skills" in prompt:
            return json.dumps([{"skill": "Docker", "confidence": 0.82, "source": "projects"}])
        if "expert technical recruiter" in prompt:
            return json.dumps(
                {
                    "overall_match_summary": "Good backend match.",
                    "skill_matches": [
                        {"skill": "Python", "candidate_has": True, "confidence": 0.95, "notes": "Listed"},
                        {"skill": "FastAPI", "candidate_has": True, "confidence": 0.9, "notes": "Listed"},
                        {"skill": "Docker", "candidate_has": True, "confidence": 0.82, "notes": "Inferred"},
                    ],
                    "experience_match": {"years_required": 2, "years_candidate": 3, "match_score": 0.9},
                    "strengths": ["Python APIs"],
                    "gaps": [],
                    "recommendation": "strong_fit",
                    "confidence": 0.9,
                }
            )
        return json.dumps(
            {
                "name": "Jane Doe",
                "email": "jane@example.com",
                "phone": "555",
                "summary": "Backend engineer",
                "skills": ["Python", "FastAPI"],
                "experience": [{"company": "Acme", "role": "Engineer", "duration": "2021-2024", "description": "Built APIs"}],
                "education": [{"institution": "Uni", "degree": "BS CS", "year": "2021"}],
                "projects": [{"name": "API", "description": "FastAPI project", "tech_stack": ["Python"], "url": None}],
                "certifications": [],
                "github_username": "jane",
                "leetcode_username": None,
                "codeforces_username": None,
                "codechef_username": None,
            }
        )


class BrokenRouter:
    async def generate(self, prompt: str, **kwargs):
        from llm.exceptions import LLMUnavailableError

        raise LLMUnavailableError("both providers unavailable")


@pytest.mark.asyncio
async def test_pipeline_steps_in_isolation(mock_db, monkeypatch, tmp_path, caplog):
    ingest = await ingest_resume(FakeUpload(), mock_db)
    assert ingest["resume_id"]
    assert "Receiving resume upload" in caplog.text

    raw_text = await extract_text_from_pdf(resume_id=ingest["resume_id"], raw_pdf_bytes=ingest["raw_bytes"])
    assert "Jane Doe" in raw_text

    router = FakeRouter()
    structured = await structure_resume(resume_id=ingest["resume_id"], raw_text=raw_text, llm_router=router)
    assert structured["name"] == "Jane Doe"

    async def fake_github(username):
        return {"username": username, "languages": ["Python"], "top_repositories": [{"stars": 10}]}

    monkeypatch.setattr("pipeline.step4_enrich.fetch_github_profile", fake_github)
    monkeypatch.setattr("pipeline.step4_enrich.fetch_leetcode_profile", lambda username: async_empty())
    monkeypatch.setattr("pipeline.step4_enrich.fetch_codeforces_profile", lambda username: async_empty())
    monkeypatch.setattr("pipeline.step4_enrich.fetch_codechef_profile", lambda username: async_empty())
    enrichment = await enrich_profile(resume_id=ingest["resume_id"], structured_resume=structured)
    assert enrichment["github_data"]["languages"] == ["Python"]

    candidate = await infer_skills(
        resume_id=ingest["resume_id"],
        candidate_profile={**structured, **enrichment},
        llm_router=router,
    )
    assert any(skill["skill"] == "Docker" for skill in candidate["skills"])

    job = await process_job_description(jd_text="Need Python FastAPI backend engineer with Docker.", db=mock_db, llm_router=router)
    assert job["title"] == "Backend Engineer"

    embeddings = await generate_embeddings(resume_id=ingest["resume_id"], candidate_profile=candidate, job=job)
    assert embeddings["candidate_embedding"].shape[0] == 384

    store = FaissJobStore(job["job_id"], index_dir=str(tmp_path))
    rag = await run_rag_pipeline(
        resume_id=ingest["resume_id"],
        job_id=job["job_id"],
        jd_text=embeddings["jd_text"],
        candidate_embedding=embeddings["candidate_embedding"],
        store=store,
    )
    assert rag["chunks"]

    evaluation = await evaluate_candidate(
        resume_id=ingest["resume_id"],
        candidate_profile=candidate,
        job=job,
        rag_context=rag["context"],
        llm_router=router,
    )
    assert evaluation["recommendation"] == "strong_fit"

    score = ScoreResult(
        final_score=88.0,
        base_score=45.0,
        preferred_bonus=10.0,
        experience_score=18.0,
        enrichment_score=15.0,
        penalties=0.0,
    )
    persisted = await persist_results(
        db=mock_db,
        resume_id=ingest["resume_id"],
        candidate_profile=candidate,
        job_id=job["job_id"],
        evaluation=evaluation,
        score_result=score,
        candidate_embedding_b64=embeddings["candidate_embedding_b64"],
        jd_embedding_b64=embeddings["jd_embedding_b64"],
    )
    assert persisted["candidate_id"]

    ranking = await rank_candidates(db=mock_db, job_id=job["job_id"])
    assert ranking["candidates"][0]["final_score"] == 88.0


@pytest.mark.asyncio
async def test_jd_processing_uses_fallback_when_llm_is_unavailable(mock_db):
    job = await process_job_description(
        jd_text="We need a Backend Engineer with 3+ years experience in Python, FastAPI, MongoDB, REST APIs, Docker, CI/CD, and cloud deployment.",
        db=mock_db,
        llm_router=BrokenRouter(),
    )

    assert job["title"] == "Backend Engineer"
    assert job["experience_years_min"] == 3
    required_skills = {item["skill"] for item in job["required_skills"]}
    assert "Python" in required_skills
    assert "FastAPI" in required_skills
    assert await mock_db.jobs.count_documents({}) == 1


@pytest.mark.asyncio
async def test_resume_structuring_uses_fallback_when_llm_is_unavailable():
    structured = await structure_resume(
        resume_id="resume_test",
        raw_text=(
            "Jane Doe\n"
            "jane@example.com\n"
            "GitHub: janedoe\n"
            "Skills: Python FastAPI MongoDB Docker REST APIs\n"
            "Project: Built a backend API."
        ),
        llm_router=BrokenRouter(),
    )

    assert structured["name"] == "Jane Doe"
    assert structured["email"] == "jane@example.com"
    assert "Python" in structured["skills"]
    assert structured["github_username"] == "janedoe"


@pytest.mark.asyncio
async def test_candidate_evaluation_uses_fallback_when_llm_is_unavailable():
    evaluation = await evaluate_candidate(
        resume_id="resume_test",
        candidate_profile={
            "skills": [
                {"skill": "Python", "source": "resume", "confidence": 1.0},
                {"skill": "FastAPI", "source": "resume", "confidence": 1.0},
            ]
        },
        job={
            "required_skills": [{"skill": "Python", "weight": 0.6}, {"skill": "FastAPI", "weight": 0.4}],
            "preferred_skills": [{"skill": "Docker", "weight": 1.0}],
            "experience_years_min": 2,
        },
        rag_context="Python backend API experience",
        llm_router=BrokenRouter(),
    )

    assert evaluation["recommendation"] == "strong_fit"
    assert evaluation["skill_matches"][0]["candidate_has"] is True


async def async_empty():
    return {}
