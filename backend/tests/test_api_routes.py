import httpx
import pytest
import respx

from api.dependencies import get_db
from db.models import ResumeStatus
from main import app


VALID_JD = (
    "Senior Backend Engineer with 3+ years experience. Required: Python, FastAPI, "
    "MongoDB, REST APIs. Preferred: Docker, AWS, CI/CD."
)


@pytest.fixture
async def api_client(mock_db, monkeypatch, tmp_path):
    monkeypatch.setattr("config.settings.faiss_index_dir", str(tmp_path))
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, mock_db
    app.dependency_overrides.clear()


async def _create_job(client: httpx.AsyncClient, jd_text: str = VALID_JD) -> dict:
    response = await client.post("/jobs/create", json={"jd_text": jd_text, "hr_user_id": "hr_test"})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_health_endpoint(api_client):
    client, _ = api_client

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_jobs_create_accepts_canonical_json(api_client):
    client, _ = api_client

    response = await client.post("/jobs/create", json={"jd_text": VALID_JD, "hr_user_id": "hr_json"})

    body = response.json()
    assert response.status_code == 200
    assert body["job_id"].startswith("job_")
    assert body["hr_user_id"] == "hr_json"
    assert body["raw_jd_text"] == VALID_JD
    assert body["evaluation_status"] == "not_started"
    assert body["title"] == "Backend Engineer"
    assert {item["skill"] for item in body["required_skills"]} >= {"Python", "FastAPI", "MongoDB", "REST APIs"}
    assert {item["skill"] for item in body["preferred_skills"]} >= {"Docker", "AWS", "CI/CD"}
    assert body["experience_years_min"] == 3
    assert body["application_window_closed"] is False


@pytest.mark.asyncio
async def test_jobs_create_accepts_common_json_alias(api_client):
    client, _ = api_client

    response = await client.post("/jobs/create", json={"job_description": VALID_JD})

    body = response.json()
    assert response.status_code == 200
    assert body["raw_jd_text"] == VALID_JD
    assert body["required_skills"]


@pytest.mark.asyncio
async def test_jobs_create_accepts_form_payload(api_client):
    client, _ = api_client

    response = await client.post("/jobs/create", data={"description": VALID_JD, "hrUserId": "hr_form"})

    body = response.json()
    assert response.status_code == 200
    assert body["hr_user_id"] == "hr_form"
    assert body["raw_jd_text"] == VALID_JD
    assert body["required_skills"]


@pytest.mark.asyncio
async def test_jobs_create_accepts_raw_text_payload(api_client):
    client, _ = api_client

    response = await client.post("/jobs/create", content=VALID_JD, headers={"content-type": "text/plain"})

    body = response.json()
    assert response.status_code == 200
    assert body["raw_jd_text"] == VALID_JD
    assert body["required_skills"]


@pytest.mark.asyncio
async def test_jobs_create_returns_400_instead_of_422_for_bad_payloads(api_client):
    client, _ = api_client

    missing = await client.post("/jobs/create", json={"role": "Backend Engineer"})
    short = await client.post("/jobs/create", json={"jd_text": "too short"})

    assert missing.status_code == 400
    assert "jd_text is required" in missing.json()["detail"]
    assert short.status_code == 400
    assert short.json() == {"detail": "jd_text must be at least 20 characters"}


@pytest.mark.asyncio
async def test_job_get_and_missing_job(api_client):
    client, _ = api_client
    job = await _create_job(client)

    existing = await client.get(f"/jobs/{job['job_id']}")
    missing = await client.get("/jobs/job_missing")

    assert existing.status_code == 200
    assert existing.json()["job_id"] == job["job_id"]
    assert missing.status_code == 404
    assert missing.json() == {"detail": "job_id not found"}


@pytest.mark.asyncio
async def test_upload_resume_and_status_flow(api_client):
    client, _ = api_client
    job = await _create_job(client)
    resume_text = (
        b"Jane Doe\njane@example.com\nSkills: Python FastAPI MongoDB Docker\n"
        b"Projects\nBuilt a FastAPI backend with MongoDB.\n"
        b"Experience\nBuilt APIs using Python and FastAPI.\n"
    )

    upload = await client.post(
        "/upload/resume",
        data={"job_id": job["job_id"], "github_url": "https://github.com/jane"},
        files={"file": ("resume.txt", resume_text, "text/plain")},
    )

    upload_body = upload.json()
    assert upload.status_code == 200, upload.text
    assert upload_body["job_id"] == job["job_id"]
    assert upload_body["status"] == "uploaded"

    status = await client.get(f"/status/{upload_body['resume_id']}")

    status_body = status.json()
    assert status.status_code == 200
    assert status_body["job_id"] == job["job_id"]
    assert status_body["candidate_id"].startswith("candidate_")
    assert status_body["status"] == ResumeStatus.ready_for_evaluation.value
    assert status_body["chunk_count"] > 0


@pytest.mark.asyncio
async def test_resume_pdf_endpoint_serves_validated_pdf_bytes(api_client):
    client, db = api_client
    cloudinary_url = "https://res.cloudinary.com/demo/image/upload/v1/resumes/resume_api"
    await db.resumes.insert_one(
        {
            "resume_id": "resume_pdf",
            "filename": "resume.pdf",
            "cloudinary_url": cloudinary_url,
            "status": ResumeStatus.completed.value,
        }
    )

    with respx.mock(assert_all_called=False) as router:
        router.get(cloudinary_url).mock(return_value=httpx.Response(404))
        router.get(cloudinary_url.replace("/image/upload/", "/raw/upload/")).mock(
            return_value=httpx.Response(200, content=b"%PDF-1.4\n%test\n", headers={"content-type": "application/pdf"})
        )

        response = await client.get("/resume/resume_pdf/pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"] == 'inline; filename="resume.pdf"'


@pytest.mark.asyncio
async def test_resume_view_generates_pdf_from_extracted_text_when_storage_is_unavailable(api_client):
    client, db = api_client
    await db.resumes.insert_one(
        {
            "resume_id": "resume_text_view",
            "filename": "resume.pdf",
            "cloudinary_url": "mock://cloudinary/resume_text_view/resume.pdf",
            "raw_text": "Jane Doe\nPython FastAPI MongoDB",
            "status": ResumeStatus.completed.value,
        }
    )

    response = await client.get("/resume/resume_text_view/view")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_evaluation_status_rejects_ranking_until_complete(api_client):
    client, _ = api_client
    job = await _create_job(client)

    status = await client.get(f"/jobs/{job['job_id']}/evaluation/status")
    ranking = await client.get(f"/jobs/{job['job_id']}/candidates")

    assert status.status_code == 200
    assert status.json()["evaluation_status"] == "not_started"
    assert ranking.status_code == 409
    assert ranking.json() == {"detail": "Evaluation has not completed for this job"}


@pytest.mark.asyncio
async def test_dashboard_candidate_and_ranking_routes(api_client):
    client, db = api_client
    job = await _create_job(client)
    await db.jobs.update_one({"job_id": job["job_id"]}, {"$set": {"evaluation_status": "completed"}})
    await db.resumes.insert_one(
        {
            "resume_id": "resume_api",
            "candidate_id": "candidate_api",
            "job_id": job["job_id"],
            "filename": "resume.txt",
            "status": ResumeStatus.completed.value,
        }
    )
    await db.candidates.insert_one(
        {
            "candidate_id": "candidate_api",
            "resume_id": "resume_api",
            "job_id": job["job_id"],
            "name": "Jane Doe",
            "email": "jane@example.com",
            "summary": "Backend engineer",
            "github_username": "jane",
        }
    )
    await db.scores.insert_one(
        {
            "score_id": "score_api",
            "candidate_id": "candidate_api",
            "resume_id": "resume_api",
            "job_id": job["job_id"],
            "final_score": 88.5,
            "base_score": 70.0,
            "preferred_bonus": 10.0,
            "experience_score": 5.0,
            "enrichment_score": 3.5,
            "penalties": 0.0,
            "recommendation": "strong_fit",
            "strengths": ["Python"],
            "gaps": ["Kubernetes"],
            "skill_matches": [],
            "evidence_chunks": {},
            "overall_explanation": "Strong backend match.",
            "subscores_detail": {
                "skill_scores": [
                    {
                        "skill": "Python",
                        "requirement_type": "required",
                        "weight": 1.0,
                        "max_points": 70.0,
                        "score": 70.0,
                        "match_percentage": 100.0,
                        "candidate_has": True,
                    }
                ],
                "penalty_detail": "none",
            },
            "created_at": 1,
        }
    )

    ranking = await client.get(f"/jobs/{job['job_id']}/candidates?page=1&page_size=10")
    job_candidate = await client.get(f"/jobs/{job['job_id']}/candidates/candidate_api")
    candidate = await client.get("/candidate/candidate_api")
    candidate_alias = await client.get("/candidates/candidate_api")
    dashboard = await client.get("/dashboard")

    assert ranking.status_code == 200
    assert ranking.json()["candidates"][0]["candidate_id"] == "candidate_api"
    assert ranking.json()["candidates"][0]["skill_scores"][0]["skill"] == "Python"
    assert ranking.json()["candidates"][0]["pros"] == ["Python"]
    assert ranking.json()["candidates"][0]["cons"] == ["Kubernetes"]
    assert job_candidate.status_code == 200
    assert job_candidate.json()["final_score"] == 88.5
    assert job_candidate.json()["skill_scores"][0]["score"] == 70.0
    assert candidate.status_code == 200
    assert candidate.json()["scores"][0]["score_id"] == "score_api"
    assert candidate_alias.status_code == 200
    assert dashboard.status_code == 200
    assert dashboard.json()["total_jobs"] == 1
    assert dashboard.json()["total_candidates"] == 1
