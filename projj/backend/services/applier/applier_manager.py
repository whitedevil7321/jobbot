"""Manages the application queue and routes jobs to the correct applier."""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright

from backend.config import settings
from backend.services.applier.base_applier import ApplyStatus
from backend.services.applier.generic_applier import GenericApplier
from backend.services.applier.linkedin_applier import LinkedInApplier

logger = logging.getLogger(__name__)

# Priority queue: (priority_value, job_id) — lower value = higher priority
# Telegram jobs: priority 0 (highest), scraped jobs: priority 1
_apply_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
_browser = None
_playwright_instance = None
_browser_context = None
_notifier = None  # Set by telegram bot module


def set_notifier(notifier_fn):
    global _notifier
    _notifier = notifier_fn


def enqueue_job(job_id: int, is_telegram: bool = False):
    priority = 0 if is_telegram else 1
    _apply_queue.put_nowait((priority, job_id))
    logger.info(f"Enqueued job {job_id} with priority {priority}")


async def _get_browser_context():
    global _browser, _playwright_instance, _browser_context
    if _browser_context:
        return _browser_context
    _playwright_instance = await async_playwright().start()
    _browser = await _playwright_instance.chromium.launch(
        headless=settings.headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ],
    )
    _browser_context = await _browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )
    await _browser_context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    return _browser_context


async def process_queue():
    """Continuously process the application queue."""
    from backend.database import SessionLocal
    from backend.models.job import Job, JobApplication

    logger.info("Application queue processor started")

    while True:
        try:
            priority, job_id = await asyncio.wait_for(_apply_queue.get(), timeout=5.0)
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Queue error: {e}")
            await asyncio.sleep(1)
            continue

        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.warning(f"Job {job_id} not found in DB")
                continue

            if job.status in ("applied", "skipped"):
                logger.info(f"Job {job_id} already processed, skipping")
                continue

            from backend.models.user_profile import UserProfile
            profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
            if not profile:
                logger.warning("No user profile found, cannot apply")
                continue

            # Create application record
            application = JobApplication(
                job_id=job_id,
                status="in_progress",
                started_at=datetime.utcnow(),
            )
            db.add(application)
            job.status = "applying"
            db.commit()
            db.refresh(application)

            logger.info(f"Applying to job {job_id}: {job.title} at {job.company}")

            # Get browser context
            context = await _get_browser_context()

            # Route to correct applier
            applier = _get_applier(job, context, profile)
            result = await applier.apply()

            # Update records
            application.status = result.status.value
            application.completed_at = datetime.utcnow()
            application.cover_letter_text = result.cover_letter_used
            application.screenshot_path = result.screenshot_path
            application.error_message = result.error
            application.stuck_reason = result.stuck_reason
            application.stuck_field = result.stuck_field
            if result.screening_answers:
                application.screening_answers = json.dumps(result.screening_answers)

            if result.status == ApplyStatus.SUBMITTED:
                job.status = "applied"
                logger.info(f"Successfully applied to job {job_id}")
                if _notifier:
                    await _notifier(
                        f"✅ Applied to *{job.title}* at *{job.company}*\n{job.url}"
                    )
            elif result.status == ApplyStatus.STUCK:
                job.status = "new"  # Reset so it can be retried
                application.status = "stuck"
                logger.warning(f"Stuck on job {job_id}: {result.stuck_reason}")
                if _notifier:
                    await _handle_stuck(db, application, job, result)
            elif result.status == ApplyStatus.ALREADY_APPLIED:
                job.status = "applied"
            elif result.status == ApplyStatus.FAILED:
                job.status = "failed"
                logger.error(f"Failed to apply to job {job_id}: {result.error}")
                if _notifier:
                    await _notifier(
                        f"❌ Failed to apply to *{job.title}*\nReason: {result.error or 'Unknown error'}"
                    )

            db.commit()

        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()
            _apply_queue.task_done()

        await asyncio.sleep(2)


async def _handle_stuck(db, application, job, result):
    """Notify user via Telegram when stuck and wait for decision."""
    from backend.models.telegram_session import PendingDecision

    message = (
        f"⚠️ Stuck on *{job.title}* at *{job.company}*\n"
        f"Reason: {result.stuck_reason or 'Unknown'}\n"
        f"URL: {job.url}\n\n"
        f"What should I do?\n"
        f"Reply with:\n"
        f"• skip - skip this job\n"
        f"• retry - try again\n"
        f"• manual - I'll apply manually"
    )

    msg_id = await _notifier(message, with_buttons=True, application_id=application.id)

    # Create pending decision record
    decision = PendingDecision(
        application_id=application.id,
        telegram_msg_id=msg_id,
        question=result.stuck_reason or "Unknown issue",
        options=json.dumps(["skip", "retry", "manual"]),
    )
    db.add(decision)
    db.commit()


def _get_applier(job, context, profile):
    url = (job.url or "").lower()
    if "linkedin.com" in url:
        return LinkedInApplier(context, profile, job)
    return GenericApplier(context, profile, job)


async def stop_browser():
    global _browser, _playwright_instance, _browser_context
    if _browser_context:
        await _browser_context.close()
        _browser_context = None
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright_instance:
        await _playwright_instance.stop()
        _playwright_instance = None
