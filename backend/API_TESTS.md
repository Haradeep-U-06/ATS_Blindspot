# API Test Guide

Base URL:

```bash
BASE_URL=http://127.0.0.1:8000
```

Start the API from the backend directory so imports and local paths are simple:

```bash
cd backend
uvicorn main:app --reload
```

The app now routes LLM calls in this order: OpenRouter primary, Groq secondary, Ollama fallback. Resume upload only parses, enriches, and vectorizes. Candidate scoring starts only after the HR evaluation trigger is called.

## GET /health

```bash
curl -s "$BASE_URL/health"
```

Expected `200 OK`:

```json
{"status":"ok"}
```

## POST /jobs/create

Canonical JSON request:

```bash
curl -s -X POST "$BASE_URL/jobs/create" \
  -H "Content-Type: application/json" \
  -H "X-HR-User-Id: hr_demo" \
  -d '{
    "jd_text": "Senior Backend Engineer with 3+ years experience. Required: Python, FastAPI, MongoDB, REST APIs. Preferred: Docker, AWS, CI/CD.",
    "hr_user_id": "hr_demo"
  }'
```

Also accepted:

```bash
curl -s -X POST "$BASE_URL/jobs/create" \
  -H "Content-Type: application/json" \
  -d '{"job_description":"Senior Backend Engineer with 3+ years experience. Required: Python, FastAPI, MongoDB, REST APIs. Preferred: Docker, AWS, CI/CD."}'

curl -s -X POST "$BASE_URL/jobs/create" \
  -d "description=Senior Backend Engineer with 3+ years experience. Required: Python, FastAPI, MongoDB, REST APIs. Preferred: Docker, AWS, CI/CD."

curl -s -X POST "$BASE_URL/jobs/create" \
  -H "Content-Type: text/plain" \
  --data-binary "Senior Backend Engineer with 3+ years experience. Required: Python, FastAPI, MongoDB, REST APIs. Preferred: Docker, AWS, CI/CD."
```

Accepted JD field names are `jd_text`, `job_description`, `description`, `raw_jd_text`, `jd`, and `text`. Accepted HR id field names are `hr_user_id`, `hrUserId`, `hr_id`, and `user_id`.

Expected `200 OK` shape:

```json
{
  "job_id": "job_<uuid>",
  "hr_user_id": "hr_demo",
  "title": "Backend Engineer",
  "raw_jd_text": "...",
  "required_skills": [
    {"skill": "Python", "weight": 0.25},
    {"skill": "FastAPI", "weight": 0.25},
    {"skill": "MongoDB", "weight": 0.25},
    {"skill": "REST APIs", "weight": 0.25}
  ],
  "preferred_skills": [
    {"skill": "Docker", "weight": 0.3333333333333333},
    {"skill": "AWS", "weight": 0.3333333333333333},
    {"skill": "CI/CD", "weight": 0.3333333333333333}
  ],
  "experience_years_min": 3,
  "domain": "Backend Engineering",
  "tech_vs_nontechnical_ratio": 1.0,
  "key_responsibilities": ["..."],
  "application_window_closed": false,
  "evaluation_status": "not_started",
  "evaluation_error": null
}
```

Exact skills and weights can vary when a configured LLM provider is available. If all remote/local LLM providers are unavailable, the deterministic fallback extracts the visible technical skills from the JD text.

Expected validation errors:

```json
{"detail":"jd_text is required. Send JSON with jd_text, job_description, description, raw_jd_text, jd, or text."}
{"detail":"jd_text must be at least 20 characters"}
{"detail":"Invalid JSON body"}
```

Save the returned id:

```bash
JOB_ID=job_<uuid>
```

Use either the saved variable or the literal id. Do not put `$` before the literal `job_...` id, because the shell will treat it as a variable and send `/jobs/`.

```bash
curl -s "$BASE_URL/jobs/$JOB_ID"
curl -s "$BASE_URL/jobs/job_<uuid>"
```

## GET /jobs/{job_id}

```bash
curl -s "$BASE_URL/jobs/$JOB_ID"
```

Expected `200 OK`: the stored job document. Before evaluation, `required_skills` and `preferred_skills` should already be populated, while `evaluation_status` remains `not_started`.

Expected error for a missing job:

```json
{"detail":"job_id not found"}
```

## POST /upload/resume

```bash
curl -s -X POST "$BASE_URL/upload/resume" \
  -F "job_id=$JOB_ID" \
  -F "file=@/absolute/path/to/resume.pdf" \
  -F "github_url=https://github.com/example-user" \
  -F "leetcode_url=https://leetcode.com/u/example-user/" \
  -F "codeforces_url=https://codeforces.com/profile/example-user" \
  -F "codechef_url=https://www.codechef.com/users/example-user"
```

Expected `200 OK` shape:

```json
{
  "resume_id": "resume_<uuid>",
  "job_id": "job_<uuid>",
  "cloudinary_url": "mock://cloudinary/resume_<uuid>/resume.pdf",
  "status": "uploaded",
  "processing": "parse_enrich_vectorize",
  "scoring_started": false
}
```

If Cloudinary credentials are configured, `cloudinary_url` will be a real Cloudinary URL instead of `mock://...`.

Save the returned id:

```bash
RESUME_ID=resume_<uuid>
```

Common errors:

```json
{"detail":"job_id not found"}
{"detail":"Application window is closed for this job"}
{"detail":"Only PDF, DOCX, or TXT resumes are allowed"}
{"detail":"Uploaded file is empty"}
{"detail":"Resume exceeds 10MB limit"}
```

## GET /status/{resume_id}

```bash
curl -s "$BASE_URL/status/$RESUME_ID"
```

Expected `200 OK` shape after background processing finishes:

```json
{
  "resume_id": "resume_<uuid>",
  "candidate_id": "candidate_<uuid>",
  "job_id": "job_<uuid>",
  "filename": "resume.pdf",
  "status": "ready_for_evaluation",
  "raw_text": "...",
  "chunk_count": 5,
  "error_message": null
}
```

During processing, `status` may be `uploaded`, `parsing`, `enriching`, or `vectorizing`. Failure states include `parse_failed`, `vector_failed`, and `failed`.

## POST /jobs/{job_id}/evaluation/trigger

Call this only after uploaded resumes have reached `ready_for_evaluation`.

```bash
curl -s -X POST "$BASE_URL/jobs/$JOB_ID/evaluation/trigger"
```

Expected `200 OK`:

```json
{
  "job_id": "job_<uuid>",
  "application_window_closed": true,
  "evaluation_status": "queued",
  "resumes_to_evaluate": 1
}
```

This is a successful trigger response. `queued` means the API accepted the HR trigger and started scoring in a background task after returning the HTTP response. `resumes_to_evaluate` is the number of resumes for this job currently in `ready_for_evaluation` or `completed` status.

Expected `409 Conflict` if resumes are still parsing/vectorizing:

```json
{"detail":"1 resumes are still being vectorized"}
```

## GET /jobs/{job_id}/evaluation/status

```bash
curl -s "$BASE_URL/jobs/$JOB_ID/evaluation/status"
```

Expected `200 OK` shape:

```json
{
  "job_id": "job_<uuid>",
  "application_window_closed": true,
  "evaluation_status": "completed",
  "evaluation_error": null,
  "resume_counts": {
    "uploaded": 0,
    "processing": 0,
    "ready_for_evaluation": 0,
    "evaluating": 0,
    "completed": 1,
    "failed": 0
  }
}
```

`evaluation_status` can be `not_started`, `queued`, `processing`, `completed`, or `completed_with_errors`.

If you changed evaluation or scoring code after a job already completed, restart the server and call the trigger endpoint again for the same job. The endpoint reevaluates resumes in `completed` status and overwrites the previous score documents.

## GET /jobs/{job_id}/candidates

```bash
curl -s "$BASE_URL/jobs/$JOB_ID/candidates?page=1&page_size=20"
```

Expected `200 OK` shape after evaluation completes:

```json
{
  "job_id": "job_<uuid>",
  "page": 1,
  "page_size": 20,
  "total": 1,
  "candidates": [
    {
      "rank": 1,
      "candidate_id": "candidate_<uuid>",
      "name": "Jane Doe",
      "email": "jane@example.com",
      "summary": "...",
      "skills": [],
      "final_score": 82.5,
      "recommendation": "strong_fit",
      "score_breakdown": {
        "base_score": 70.0,
        "preferred_bonus": 5.0,
        "experience_score": 5.0,
        "enrichment_score": 2.5,
        "penalties": 0.0
      }
    }
  ]
}
```

Expected `409 Conflict` before evaluation finishes:

```json
{"detail":"Evaluation has not completed for this job"}
```

## GET /jobs/{job_id}/candidates/{candidate_id}

```bash
CANDIDATE_ID=candidate_<uuid>
curl -s "$BASE_URL/jobs/$JOB_ID/candidates/$CANDIDATE_ID"
```

Expected `200 OK` shape:

```json
{
  "job_id": "job_<uuid>",
  "candidate_id": "candidate_<uuid>",
  "resume_id": "resume_<uuid>",
  "summary": {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "",
    "resume_summary": "...",
    "external_profiles": {
      "github": "example-user",
      "leetcode": "example-user",
      "codeforces": "example-user",
      "codechef": "example-user"
    }
  },
  "final_score": 82.5,
  "skill_scores": [],
  "evidence_chunks": {},
  "strengths": [],
  "weaknesses": [],
  "explanation": "...",
  "score_breakdown": {
    "required_skill_score": 70.0,
    "preferred_skill_score": 5.0,
    "evidence_quality_score": 5.0,
    "confidence_score": 2.5,
    "penalties": 0.0,
    "details": {}
  }
}
```

## GET /candidate/{candidate_id}

```bash
curl -s "$BASE_URL/candidate/$CANDIDATE_ID"
```

Expected `200 OK`: candidate profile plus a `scores` array sorted newest first.

## GET /candidates/{candidate_id}

```bash
curl -s "$BASE_URL/candidates/$CANDIDATE_ID"
```

Expected `200 OK`: same response shape as `/candidate/{candidate_id}`.

## GET /dashboard

```bash
curl -s "$BASE_URL/dashboard"
```

Expected `200 OK` shape:

```json
{
  "total_jobs": 1,
  "total_candidates": 1,
  "total_resumes": 1,
  "completed_resumes": 1,
  "failed_resumes": 0,
  "latest_jobs": [],
  "top_scores": []
}
```

The arrays contain recent job and score documents when data exists.

## Built-in FastAPI Docs

These are generated by FastAPI and do not hit application business logic:

```bash
curl -I "$BASE_URL/docs"
curl -s "$BASE_URL/openapi.json"
curl -I "$BASE_URL/redoc"
```

Expected results: `/docs` and `/redoc` return HTML, and `/openapi.json` returns the OpenAPI schema containing the routes listed above.
