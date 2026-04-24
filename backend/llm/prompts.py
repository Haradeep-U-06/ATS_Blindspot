JSON_ONLY_SUFFIX = "Return ONLY valid JSON. No markdown code blocks. No explanation text."

JD_STRUCTURE_PROMPT = """
Parse this Job Description and return a JSON object with only the technical stack needed for scoring.
Do not include soft skills, responsibilities, personality traits, or inferred skills.
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
You are an expert technical recruiter. Evaluate only the technical skills from the job description.
Use only the provided evidence chunks. Do not infer hidden skills. Do not give credit for a skill unless a chunk explicitly supports it.
Return a JSON object with:
- overall_match_summary (string, 2-3 sentences)
- skill_matches (array of objects: {{skill, candidate_has, confidence, notes, evidence, evidence_sources}})
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
