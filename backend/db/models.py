from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def model_to_dict(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


class ResumeStatus(str, Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    enriching = "enriching"
    scoring = "scoring"
    completed = "completed"
    parse_failed = "parse_failed"
    failed = "failed"


class SkillItem(BaseModel):
    skill: str
    source: str = "resume"
    confidence: float = 1.0


class WeightedSkill(BaseModel):
    skill: str
    weight: float


class ExperienceItem(BaseModel):
    company: str = ""
    role: str = ""
    duration: str = ""
    description: str = ""


class EducationItem(BaseModel):
    institution: str = ""
    degree: str = ""
    year: str = ""


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    tech_stack: List[str] = Field(default_factory=list)
    url: Optional[str] = None


class ResumeDocument(BaseModel):
    resume_id: str = Field(default_factory=lambda: new_id("resume"))
    candidate_id: Optional[str] = None
    cloudinary_url: Optional[str] = None
    filename: str
    upload_timestamp: datetime = Field(default_factory=utc_now)
    status: ResumeStatus = ResumeStatus.uploaded
    error_message: Optional[str] = None


class CandidateDocument(BaseModel):
    candidate_id: str = Field(default_factory=lambda: new_id("candidate"))
    resume_id: str
    name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""
    skills: List[SkillItem] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    github_username: Optional[str] = None
    leetcode_username: Optional[str] = None
    codeforces_username: Optional[str] = None
    codechef_username: Optional[str] = None
    github_data: Dict[str, Any] = Field(default_factory=dict)
    leetcode_data: Dict[str, Any] = Field(default_factory=dict)
    codeforces_data: Dict[str, Any] = Field(default_factory=dict)
    codechef_data: Dict[str, Any] = Field(default_factory=dict)
    embedding_b64: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ScoreDocument(BaseModel):
    score_id: str = Field(default_factory=lambda: new_id("score"))
    candidate_id: str
    job_id: str
    final_score: float
    base_score: float
    preferred_bonus: float
    experience_score: float
    enrichment_score: float
    penalties: float
    recommendation: str
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    skill_matches: List[Dict[str, Any]] = Field(default_factory=list)
    subscores_detail: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class JobDocument(BaseModel):
    job_id: str = Field(default_factory=lambda: new_id("job"))
    hr_user_id: str = "default_hr"
    title: str
    raw_jd_text: str
    required_skills: List[WeightedSkill] = Field(default_factory=list)
    preferred_skills: List[WeightedSkill] = Field(default_factory=list)
    experience_years_min: int = 0
    domain: str = ""
    tech_vs_nontechnical_ratio: float = 1.0
    key_responsibilities: List[str] = Field(default_factory=list)
    embedding_b64: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class ScoreResult(BaseModel):
    final_score: float
    base_score: float
    preferred_bonus: float
    experience_score: float
    enrichment_score: float
    penalties: float
    subscores_detail: Dict[str, Any] = Field(default_factory=dict)
