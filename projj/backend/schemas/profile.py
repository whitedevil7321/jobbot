from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserProfileBase(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    years_of_exp: int = 0
    work_auth: str = "citizen"
    visa_sponsorship_needed: bool = False
    target_roles: Optional[List[str]] = None
    target_domains: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    summary: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: str = "United States"
    highest_education: Optional[str] = None
    school_name: Optional[str] = None
    graduation_year: Optional[int] = None
    degree: Optional[str] = None
    gender: Optional[str] = None
    ethnicity: Optional[str] = None
    veteran_status: str = "I am not a veteran"
    disability_status: str = "I don't wish to answer"
    desired_salary_min: Optional[int] = None
    desired_salary_max: Optional[int] = None
    salary_currency: str = "USD"


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(UserProfileBase):
    pass


class UserProfileResponse(UserProfileBase):
    id: int
    resume_path: Optional[str] = None
    resume_text: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
