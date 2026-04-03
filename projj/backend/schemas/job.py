from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class JobResponse(BaseModel):
    id: int
    source: str
    url: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    remote: bool = False
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: str = "USD"
    description: Optional[str] = None
    required_exp: Optional[int] = None
    skills_required: Optional[List[str]] = None
    domain: Optional[str] = None
    visa_sponsorship: str = "unknown"
    easy_apply: bool = False
    apply_url: Optional[str] = None
    filter_score: float = 0.0
    priority: int = 0
    status: str = "new"
    scraped_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobManualSubmit(BaseModel):
    url: str
    title: Optional[str] = None
    company: Optional[str] = None


class ApplicationResponse(BaseModel):
    id: int
    job_id: int
    attempt_number: int
    status: str
    stuck_reason: Optional[str] = None
    stuck_field: Optional[str] = None
    user_response: Optional[str] = None
    cover_letter_text: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DecisionRequest(BaseModel):
    action: str  # skip|retry|manual


class ApplicationStats(BaseModel):
    total: int = 0
    pending: int = 0
    in_progress: int = 0
    submitted: int = 0
    stuck: int = 0
    skipped: int = 0
    failed: int = 0
