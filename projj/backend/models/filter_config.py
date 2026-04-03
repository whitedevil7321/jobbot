from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from backend.database import Base


class FilterConfig(Base):
    __tablename__ = "filter_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, default="default")
    is_active = Column(Boolean, default=True)
    locations = Column(Text)              # JSON array ["Remote", "New York, NY"]
    min_years_exp = Column(Integer, default=0)
    max_years_exp = Column(Integer, default=20)
    job_types = Column(Text)              # JSON ["full-time","contract","part-time"]
    domains = Column(Text)                # JSON ["Backend","Frontend","DevOps"]
    required_skills = Column(Text)        # JSON ["Python","SQL"]
    excluded_keywords = Column(Text)      # JSON ["senior","principal","director"]
    work_auth_required = Column(Text)     # JSON ["citizen","greencard"] or null=any
    # any|required|not_required
    visa_sponsorship_filter = Column(String, default="any")
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    portals = Column(Text)                # JSON ["linkedin","indeed","dice"] null=all
    created_at = Column(DateTime, server_default=func.now())
