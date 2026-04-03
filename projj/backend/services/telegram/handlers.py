"""Telegram bot message handlers."""
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from backend.services.telegram.link_parser import extract_job_url

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *JobBot is active!*\n\n"
        "Send me a job link and I'll apply to it immediately.\n\n"
        "Commands:\n"
        "/status - View application stats\n"
        "/pause - Pause auto-apply\n"
        "/resume - Resume auto-apply\n"
        "/help - Show this message",
        parse_mode="Markdown",
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *How to use JobBot:*\n\n"
        "• Send any job link and I'll apply automatically\n"
        "• I use your profile to fill all forms\n"
        "• I'll notify you when I apply or get stuck\n"
        "• Jobs sent here get *priority* over scraped jobs\n\n"
        "Open the dashboard at http://localhost:8000 to:\n"
        "• Update your profile\n"
        "• Set job filters\n"
        "• View all applications",
        parse_mode="Markdown",
    )


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from backend.database import SessionLocal
    from backend.models.job import Job, JobApplication

    db = SessionLocal()
    try:
        total_jobs = db.query(Job).count()
        applied = db.query(Job).filter(Job.status == "applied").count()
        pending = db.query(Job).filter(Job.status.in_(["queued", "applying"])).count()
        failed = db.query(Job).filter(Job.status == "failed").count()

        text = (
            f"📊 *Application Status*\n\n"
            f"Total jobs found: {total_jobs}\n"
            f"✅ Applied: {applied}\n"
            f"⏳ In queue: {pending}\n"
            f"❌ Failed: {failed}\n\n"
            f"Dashboard: http://localhost:8000"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        db.close()


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages — look for job URLs."""
    if not update.message or not update.message.text:
        return

    text = update.message.text
    url = extract_job_url(text)

    if not url:
        await update.message.reply_text(
            "I didn't find a job URL in your message. Please send a direct job link."
        )
        return

    await update.message.reply_text(f"🔍 Got it! Processing job link...\n{url}")

    from backend.database import SessionLocal
    from backend.models.job import Job
    from backend.services.applier.applier_manager import enqueue_job
    from backend.services.scraper.scraper_manager import scraper_manager

    db = SessionLocal()
    try:
        # Check if already in DB
        existing = db.query(Job).filter(Job.url == url).first()
        if existing:
            if existing.status == "applied":
                await update.message.reply_text("✅ Already applied to this job!")
                return
            # Re-enqueue with high priority
            existing.priority = 1
            existing.status = "queued"
            db.commit()
            enqueue_job(existing.id, is_telegram=True)
            await update.message.reply_text(
                f"⬆️ Moved to top of queue!\n*{existing.title}* at *{existing.company}*",
                parse_mode="Markdown",
            )
            return

        # Scrape job details
        await update.message.reply_text("📄 Fetching job details...")
        scraped = await scraper_manager.scrape_single_url(url)

        if scraped:
            job = Job(
                source=scraped.source,
                url=url,
                title=scraped.title or "Unknown Title",
                company=scraped.company,
                location=scraped.location,
                remote=scraped.remote,
                description=scraped.description,
                priority=1,
                status="queued",
                visa_sponsorship=scraped.visa_sponsorship,
                easy_apply=scraped.easy_apply,
                apply_url=scraped.apply_url or url,
            )
        else:
            job = Job(
                source="telegram",
                url=url,
                title=text[:100] if len(text) > 10 else "Job from Telegram",
                priority=1,
                status="queued",
                apply_url=url,
            )

        db.add(job)
        db.commit()
        db.refresh(job)

        enqueue_job(job.id, is_telegram=True)

        await update.message.reply_text(
            f"✅ Added to priority queue!\n\n"
            f"*{job.title}*\n"
            f"Company: {job.company or 'Unknown'}\n"
            f"Location: {job.location or 'Unknown'}\n\n"
            f"I'll apply shortly and let you know!",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"message_handler error: {e}")
        await update.message.reply_text(f"❌ Error processing job: {str(e)[:200]}")
    finally:
        db.close()


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button responses (skip/retry/manual)."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if not data.startswith("decision:"):
        return

    parts = data.split(":")
    if len(parts) != 3:
        return

    _, app_id_str, action = parts
    try:
        app_id = int(app_id_str)
    except ValueError:
        return

    from backend.database import SessionLocal
    from backend.models.telegram_session import PendingDecision
    from backend.models.job import JobApplication, Job
    from backend.services.applier.applier_manager import enqueue_job

    db = SessionLocal()
    try:
        decision = db.query(PendingDecision).filter(
            PendingDecision.application_id == app_id,
            PendingDecision.resolved == False,
        ).first()

        if not decision:
            await query.edit_message_text("This decision has already been resolved.")
            return

        decision.resolved = True
        decision.resolution = action
        decision.resolved_at = datetime.utcnow()

        application = db.query(JobApplication).filter(JobApplication.id == app_id).first()
        job = application.job if application else None

        if action == "skip":
            if application:
                application.status = "skipped"
                application.user_response = "skip"
            if job:
                job.status = "skipped"
            await query.edit_message_text(f"⏭ Skipped: *{job.title if job else 'job'}*", parse_mode="Markdown")

        elif action == "retry":
            if application:
                application.status = "pending"
                application.user_response = "retry"
            if job:
                job.status = "queued"
                enqueue_job(job.id, is_telegram=True)
            await query.edit_message_text(f"🔄 Retrying: *{job.title if job else 'job'}*", parse_mode="Markdown")

        elif action == "manual":
            if application:
                application.status = "skipped"
                application.user_response = "manual"
            if job:
                job.status = "skipped"
            await query.edit_message_text(
                f"✋ Marked for manual apply: *{job.title if job else 'job'}*\n{job.url if job else ''}",
                parse_mode="Markdown",
            )

        db.commit()
    except Exception as e:
        logger.error(f"callback_handler error: {e}")
    finally:
        db.close()


async def pause_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from backend.config import settings
    settings.auto_apply = False
    await update.message.reply_text("⏸ Auto-apply paused. Send /resume to continue.")


async def resume_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from backend.config import settings
    settings.auto_apply = True
    await update.message.reply_text("▶️ Auto-apply resumed!")
