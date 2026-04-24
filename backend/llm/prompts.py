JSON_ONLY_SUFFIX = "Return ONLY valid JSON. No markdown code blocks. No explanation text."

RESUME_STRUCTURE_PROMPT = """
Extract the following from the resume text and return a JSON object with these exact keys:
- name (string)
- email (string)
- phone (string)
- summary (string)
- skills (array of strings)
- experience (array of objects: {{company, role, duration, description}})
- education (array of objects: {{institution, degree, year}})
- projects (array of objects: {{name, description, tech_stack, url}})
- certifications (array of strings)
- github_username (string or null)
- leetcode_username (string or null)
- codeforces_username (string or null)
- codechef_username (string or null)

Resume text:
{resume_text}

Example output:
{{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "phone": "+1-555-123-4567",
  "summary": "Backend engineer with FastAPI experience.",
  "skills": ["Python", "FastAPI", "MongoDB"],
  "experience": [{{"company": "Acme", "role": "Engineer", "duration": "2022-2024", "description": "Built APIs."}}],
  "education": [{{"institution": "State University", "degree": "BS CS", "year": "2021"}}],
  "projects": [{{"name": "ATS", "description": "Resume parser", "tech_stack": ["Python"], "url": null}}],
  "certifications": [],
  "github_username": "janedoe",
  "leetcode_username": null,
  "codeforces_username": null,
  "codechef_username": null
}}
""" + JSON_ONLY_SUFFIX

SKILL_INFERENCE_PROMPT = """
Given a candidate's resume skills, projects, work experience, and GitHub repositories, infer additional technical skills they likely possess but did not explicitly list.
For each inferred skill, return a JSON array of objects with keys:
- skill (string)
- confidence (float 0.0-1.0)
- source (string: "github" | "projects" | "experience" | "leetcode")

Only include skills with confidence >= 0.6. Maximum 15 inferred skills.

Candidate context:
{candidate_context}
""" + JSON_ONLY_SUFFIX

JD_STRUCTURE_PROMPT = """
Parse this Job Description and return a JSON object with:
- title (string)
- required_skills (array of objects: {{skill, weight}} where weight is float 0.0-1.0)
- preferred_skills (array of objects: {{skill, weight}})
- experience_years_min (int)
- domain (string)
- tech_vs_nontechnical_ratio (float: 0.0 = all soft skills, 1.0 = all technical)
- key_responsibilities (array of strings)

Weights in required_skills must sum to 1.0. Weights in preferred_skills must sum to 1.0.

Job Description:
{jd_text}

Example output:
{{
  "title": "Senior Backend Engineer",
  "required_skills": [{{"skill": "Python", "weight": 0.4}}, {{"skill": "FastAPI", "weight": 0.3}}, {{"skill": "MongoDB", "weight": 0.3}}],
  "preferred_skills": [{{"skill": "Docker", "weight": 0.5}}, {{"skill": "CI/CD", "weight": 0.5}}],
  "experience_years_min": 3,
  "domain": "Backend Engineering",
  "tech_vs_nontechnical_ratio": 0.85,
  "key_responsibilities": ["Build APIs", "Own database integrations"]
}}
""" + JSON_ONLY_SUFFIX

EVALUATION_PROMPT = """
You are an expert technical recruiter. Given the candidate profile, job description, and relevant context chunks, evaluate the candidate's fit.
Return a JSON object with:
- overall_match_summary (string, 2-3 sentences)
- skill_matches (array of objects: {{skill, candidate_has, confidence, notes}})
- experience_match (object: {{years_required, years_candidate, match_score float 0-1}})
- strengths (array of strings, max 5)
- gaps (array of strings, max 5)
- recommendation (string: "strong_fit" | "moderate_fit" | "weak_fit" | "no_fit")
- confidence (float 0.0-1.0)

Candidate profile:
{candidate_profile}

Job description:
{job_description}

Relevant context chunks:
{rag_context}
""" + JSON_ONLY_SUFFIX

JSON_REPAIR_PROMPT = """
Fix this invalid JSON and return only valid JSON:
{broken_json}
""" + JSON_ONLY_SUFFIX
