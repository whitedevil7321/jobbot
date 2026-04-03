"""APScheduler setup for periodic scraping."""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.config import settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler():
    global _scheduler
    from backend.workers.scrape_worker import run_scrape
    from backend.services.applier.applier_manager import process_queue

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_scrape,
        trigger=IntervalTrigger(minutes=settings.scrape_interval_minutes),
        id="scrape_job",
        name="Scrape all job portals",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(f"Scheduler started — scraping every {settings.scrape_interval_minutes} minute(s)")


async def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


async def trigger_scrape_now():
    from backend.workers.scrape_worker import run_scrape
    await run_scrape()


def get_scheduler_status() -> dict:
    if not _scheduler:
        return {"running": False, "jobs": []}
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })
    return {"running": _scheduler.running, "jobs": jobs}
