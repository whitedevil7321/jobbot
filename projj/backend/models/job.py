from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)  # linkedin|indeed|glassdoor|ziprecruiter|dice|monster|telegram|other
    external_id = Column(String)
    url = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    company = Column(String)
    location = Column(String)
    remote = Column(Boolean, default=False)
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    currency = Column(String, default="USD")
    description = Column(Text)
    required_exp = Column(Integer)
    skills_required = Column(Text)    # JSON array
    domain = Column(String)
    visa_sponsorship = Column(String, default="unknown")  # yes|no|unknown
    work_auth_req = Column(Text)      # JSON array or null
    easy_apply = Column(Boolean, default=False)
    apply_url = Column(String)
    filter_score = Column(Float, default=0.0)
    priority = Column(Integer, default=0)  # 1=telegram, 0=scraped
    # new|queued|applying|applied|skipped|failed
    status = Column(String, default="new")
    scraped_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    applications = relationship("JobApplication", back_populates="job")


class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False, default=1)
    # pending|in_progress|submitted|stuck|skipped|failed
    status = Column(String, nullable=False, default="pending")
    stuck_reason = Column(Text)
    stuck_field = Column(String)
    user_response = Column(String)    # skip|retry|manual
    resume_used = Column(String)
    cover_letter_text = Column(Text)
    tailored_resume = Column(Text)
    screening_answers = Column(Text)  # JSON {question: answer}
    error_message = Column(Text)
    screenshot_path = Column(String)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    job = relationship("Job", back_populates="applications")
    pending_decision = relationship("PendingDecision", back_populates="application", uselist=False)
