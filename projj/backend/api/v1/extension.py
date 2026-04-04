"""
Extension-specific API endpoints for the Chrome/Edge extension.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.models.job import Job, JobApplication

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/extension", tags=["extension"])


class ExtensionResult(BaseModel):
    jobId: int
    status: str              # applied | stuck | failed
    reason: Optional[str] = None
    coverLetter: Optional[str] = None
    screeningAnswers: Optional[dict] = None


class LLMAnswerRequest(BaseModel):
    question: str
    context: Optional[str] = None
    type_hint: Optional[str] = "text"   # text | short | yes_no | radio


@router.post("/result")
def report_extension_result(data: ExtensionResult, db: Session = Depends(get_db)):
    """Called by the extension background worker when an application finishes."""
    job = db.query(Job).filter(Job.id == data.jobId).first()
    if not job:
        return {"message": "Job not found"}

    status_map = {
        "applied": "applied",
        "stuck":   "stuck",
        "failed":  "failed",
    }
    job.status = status_map.get(data.status, "failed")

    # Update or create the application record
    application = (
        db.query(JobApplication)
        .filter(JobApplication.job_id == data.jobId, JobApplication.status == "in_progress")
        .first()
    )
    if not application:
        application = JobApplication(job_id=data.jobId)
        db.add(application)

    application.completed_at = datetime.utcnow()
    application.status = "submitted" if data.status == "applied" else data.status
    if data.reason:
        application.stuck_reason = data.reason
        application.error_message = data.reason
    if data.coverLetter:
        application.cover_letter_text = data.coverLetter
    if data.screeningAnswers:
        application.screening_answers = json.dumps(data.screeningAnswers)

    db.commit()

    # Notify via Telegram if configured
    if data.status == "applied":
        _notify(f"✅ Applied to *{job.title}* at *{job.company}*\n{job.url or ''}")
    elif data.status == "stuck":
        _notify(f"⚠️ Stuck on *{job.title}* at *{job.company}*\nReason: {data.reason or 'Unknown'}\n{job.url or ''}")
    elif data.status == "failed":
        _notify(f"❌ Failed: *{job.title}* at *{job.company}*\nReason: {data.reason or 'Unknown'}")

    logger.info(f"Extension result: job {data.jobId} → {data.status}")
    return {"message": "Result recorded"}


@router.post("/ollama/answer")
async def get_llm_answer(data: LLMAnswerRequest, db: Session = Depends(get_db)):
    """
    Ask the local Ollama LLM to answer a job application question.
    Falls back to profile-based defaults if Ollama is unavailable.
    """
    from backend.models.user_profile import UserProfile
    from backend.services.llm.cover_letter import answer_question, answer_yes_no

    profile = db.query(UserProfile).filter(UserProfile.id == 1).first()

    try:
        if data.type_hint in ("yes_no", "radio"):
            answer = await answer_yes_no(data.question, profile)
        else:
            answer = await answer_question(data.question, profile, context=data.context)
        return {"answer": answer}
    except Exception as e:
        logger.warning(f"LLM answer failed: {e}")
        return {"answer": ""}


def _notify(message: str):
    """Fire-and-forget Telegram notification."""
    import asyncio
    try:
        from backend.services.telegram.notifier import send_notification
        asyncio.create_task(send_notification(message))
    except Exception:
        pass
