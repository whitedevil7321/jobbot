"""
Manages the application queue and routes jobs to the correct applier.
Uses only the GenericApplier — works on any company career page, job portal,
or direct application URL. No LinkedIn dependency.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright

from backend.config import settings
from backend.services.applier.base_applier import ApplyStatus
from backend.services.applier.generic_applier import GenericApplier

logger = logging.getLogger(__name__)

# ── Priority queue ────────────────────────────────────────────────────────────
# (priority_value, job_id) — lower value = higher priority
# Telegram / manual jobs: priority 0 (applied first)
# Scraped jobs: priority 1
_apply_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

# ── Shared browser state ──────────────────────────────────────────────────────
_browser = None
_playwright_instance = None
_browser_context = None

# ── Callbacks ─────────────────────────────────────────────────────────────────
_notifier = None        # async fn(msg, with_buttons?, application_id?) → msg_id
_broadcast = None       # async fn(dict) → None  (WebSocket)


def set_notifier(notifier_fn):
    global _notifier
    _notifier = notifier_fn


def set_broadcast(broadcast_fn):
    global _broadcast
    _broadcast = broadcast_fn


def enqueue_job(job_id: int, is_telegram: bool = False):
    priority = 0 if is_telegram else 1
    _apply_queue.put_nowait((priority, job_id))
    logger.info(f"Enqueued job {job_id} (priority={priority})")


async def _get_browser_context():
    """Return the shared Playwright browser context, creating it if needed."""
    global _browser, _playwright_instance, _browser_context
    if _browser_context:
        try:
            # Sanity-check: context still alive
            await _browser_context.pages()
            return _browser_context
        except Exception:
            # Context died — recreate
            _browser_context = None
            _browser = None
            _playwright_instance = None

    _playwright_instance = await async_playwright().start()
    _browser = await _playwright_instance.chromium.launch(
        headless=settings.headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1440,900",
        ],
    )
    _browser_context = await _browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="America/New_York",
    )
    # Remove webdriver fingerprint
    await _browser_context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    logger.info("Playwright browser context created")
    return _browser_context


async def process_queue():
    """
    Continuously process the application queue.
    Respects settings.auto_apply — if False, just logs but does not apply.
    """
    from backend.database import SessionLocal
    from backend.models.job import Job, JobApplication

    logger.info("Application queue processor started")

    while True:
        # ── Pull next job from queue ──────────────────────────────────────
        try:
            priority, job_id = await asyncio.wait_for(_apply_queue.get(), timeout=5.0)
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Queue dequeue error: {e}")
            await asyncio.sleep(1)
            continue

        if not settings.auto_apply:
            logger.info(f"auto_apply=False — skipping job {job_id}")
            _apply_queue.task_done()
            continue

        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.warning(f"Job {job_id} not found in DB")
                continue

            if job.status in ("applied", "skipped", "applying"):
                logger.info(f"Job {job_id} already processed ({job.status}), skipping")
                continue

            from backend.models.user_profile import UserProfile
            profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
            if not profile or not profile.email:
                logger.warning("No user profile or missing email — cannot apply")
                continue

            # ── Mark as applying ──────────────────────────────────────────
            application = JobApplication(
                job_id=job_id,
                status="in_progress",
                started_at=datetime.utcnow(),
            )
            db.add(application)
            job.status = "applying"
            db.commit()
            db.refresh(application)

            logger.info(f"▶ Applying to job {job_id}: {job.title} @ {job.company} — {job.apply_url or job.url}")

            # Broadcast status update
            await _safe_broadcast({
                "type": "job_updated",
                "job_id": job_id,
                "status": "applying",
            })

            # ── Get browser context ───────────────────────────────────────
            try:
                context = await _get_browser_context()
            except Exception as e:
                logger.error(f"Browser launch failed for job {job_id}: {e}")
                job.status = "failed"
                application.status = "failed"
                application.error_message = f"Browser launch failed: {e}"
                db.commit()
                continue

            # ── Apply ─────────────────────────────────────────────────────
            applier = GenericApplier(context, profile, job)
            try:
                result = await asyncio.wait_for(
                    applier.apply(),
                    timeout=300,  # 5-minute hard cap per application
                )
            except asyncio.TimeoutError:
                result_status = ApplyStatus.STUCK
                from backend.services.applier.base_applier import ApplicationResult
                result = ApplicationResult(
                    status=ApplyStatus.STUCK,
                    stuck_reason="Application timed out after 5 minutes",
                )
            except Exception as e:
                logger.error(f"Applier exception for job {job_id}: {e}")
                from backend.services.applier.base_applier import ApplicationResult
                result = ApplicationResult(
                    status=ApplyStatus.FAILED,
                    error=str(e),
                )

            # ── Save result ───────────────────────────────────────────────
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
                application.status = "submitted"
                logger.info(f"✅ Applied to job {job_id}: {job.title}")
                await _safe_broadcast({"type": "job_updated", "job_id": job_id, "status": "applied"})
                if _notifier:
                    try:
                        await _notifier(f"✅ Applied to *{job.title}* at *{job.company}*\n{job.url}")
                    except Exception:
                        pass

            elif result.status == ApplyStatus.ALREADY_APPLIED:
                job.status = "applied"
                application.status = "submitted"
                logger.info(f"Already applied to job {job_id}")
                await _safe_broadcast({"type": "job_updated", "job_id": job_id, "status": "applied"})

            elif result.status == ApplyStatus.STUCK:
                job.status = "stuck"
                application.status = "stuck"
                logger.warning(f"⚠️ Stuck on job {job_id}: {result.stuck_reason}")
                await _safe_broadcast({"type": "job_updated", "job_id": job_id, "status": "stuck"})
                if _notifier:
                    try:
                        await _handle_stuck(db, application, job, result)
                    except Exception as e:
                        logger.error(f"Stuck handler error: {e}")

            elif result.status == ApplyStatus.FAILED:
                job.status = "failed"
                application.status = "failed"
                logger.error(f"❌ Failed job {job_id}: {result.error}")
                await _safe_broadcast({"type": "job_updated", "job_id": job_id, "status": "failed"})
                if _notifier:
                    try:
                        await _notifier(
                            f"❌ Failed: *{job.title}* at *{job.company}*\n"
                            f"Reason: {result.error or 'Unknown'}"
                        )
                    except Exception:
                        pass

            db.commit()

        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()
            _apply_queue.task_done()

        # Small delay between applications to be polite
        await asyncio.sleep(3)


async def _safe_broadcast(message: dict):
    """Broadcast a WebSocket message, silently ignoring errors."""
    if _broadcast:
        try:
            await _broadcast(message)
        except Exception:
            pass


async def _handle_stuck(db, application, job, result):
    """Notify user via Telegram when stuck and record pending decision."""
    from backend.models.telegram_session import PendingDecision

    message = (
        f"⚠️ Stuck applying to *{job.title}* at *{job.company}*\n"
        f"Reason: {result.stuck_reason or 'Unknown'}\n"
        f"URL: {job.url or 'N/A'}\n\n"
        f"What should I do?"
    )

    try:
        msg_id = await _notifier(message, with_buttons=True, application_id=application.id)
    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")
        msg_id = None

    decision = PendingDecision(
        application_id=application.id,
        telegram_msg_id=msg_id,  # Can be None — that's fine
        question=result.stuck_reason or "Unknown issue",
        options=json.dumps(["skip", "retry", "manual"]),
    )
    db.add(decision)
    db.commit()


async def stop_browser():
    """Gracefully stop the shared browser instance."""
    global _browser, _playwright_instance, _browser_context
    try:
        if _browser_context:
            await _browser_context.close()
    except Exception:
        pass
    try:
        if _browser:
            await _browser.close()
    except Exception:
        pass
    try:
        if _playwright_instance:
            await _playwright_instance.stop()
    except Exception:
        pass
    finally:
        _browser_context = None
        _browser = None
        _playwright_instance = None
    logger.info("Browser stopped")
