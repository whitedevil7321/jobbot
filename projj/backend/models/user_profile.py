from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from backend.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, default=1)
    full_name = Column(String, nullable=False, default="")
    email = Column(String, nullable=False, default="")
    phone = Column(String)
    location = Column(String)
    linkedin_url = Column(String)
    github_url = Column(String)
    portfolio_url = Column(String)
    years_of_exp = Column(Integer, nullable=False, default=0)
    # citizen | greencard | h1b | opt | tn | other
    work_auth = Column(String, nullable=False, default="citizen")
    visa_sponsorship_needed = Column(Boolean, default=False)
    target_roles = Column(Text)       # JSON array
    target_domains = Column(Text)     # JSON array
    skills = Column(Text)             # JSON array
    resume_path = Column(String)
    resume_text = Column(Text)
    summary = Column(Text)
    # Additional fields for auto-applying
    address = Column(String)
    city = Column(String)
    state = Column(String)
    zip_code = Column(String)
    country = Column(String, default="United States")
    highest_education = Column(String)
    school_name = Column(String)
    graduation_year = Column(Integer)
    degree = Column(String)
    gender = Column(String)
    ethnicity = Column(String)
    veteran_status = Column(String, default="I am not a veteran")
    disability_status = Column(String, default="I don't wish to answer")
    # Salary expectations
    desired_salary_min = Column(Integer)
    desired_salary_max = Column(Integer)
    salary_currency = Column(String, default="USD")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
