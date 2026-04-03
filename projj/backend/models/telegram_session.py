from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base


class TelegramConfig(Base):
    __tablename__ = "telegram_config"

    id = Column(Integer, primary_key=True, default=1)
    bot_token = Column(String, nullable=False)
    chat_id = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PendingDecision(Base):
    __tablename__ = "pending_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("job_applications.id"), nullable=False)
    telegram_msg_id = Column(Integer)
    question = Column(Text, nullable=False)
    options = Column(Text)         # JSON ["skip","retry","manual"]
    resolved = Column(Boolean, default=False)
    resolution = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime)

    application = relationship("JobApplication", back_populates="pending_decision")
