from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from backend.database import Base


class SchedulerRun(Base):
    __tablename__ = "scheduler_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task = Column(String, nullable=False)    # scrape|apply
    status = Column(String, nullable=False)  # running|completed|failed
    jobs_found = Column(Integer, default=0)
    jobs_new = Column(Integer, default=0)
    error = Column(Text)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime)
