from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class FilterConfigBase(BaseModel):
    name: str = "default"
    is_active: bool = True
    locations: Optional[List[str]] = None
    min_years_exp: int = 0
    max_years_exp: int = 20
    job_types: Optional[List[str]] = None
    domains: Optional[List[str]] = None
    required_skills: Optional[List[str]] = None
    excluded_keywords: Optional[List[str]] = None
    work_auth_required: Optional[List[str]] = None
    visa_sponsorship_filter: str = "any"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    portals: Optional[List[str]] = None


class FilterConfigCreate(FilterConfigBase):
    pass


class FilterConfigUpdate(FilterConfigBase):
    pass


class FilterConfigResponse(FilterConfigBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
