"""Scrape worker: runs all scrapers and persists new jobs to DB."""
import json
import logging
from datetime import datetime

from backend.database import SessionLocal
from backend.models.job import Job
from backend.models.scheduler import SchedulerRun
from backend.services.scraper.scraper_manager import scraper_manager
from backend.services.filters.filter_engine import filter_engine

logger = logging.getLogger(__name__)

# WebSocket broadcast callback (set by main.py)
_broadcast_fn = None


def set_broadcast(fn):
    global _broadcast_fn
    _broadcast_fn = fn


async def run_scrape():
    """Main scrape task called by scheduler."""
    db = SessionLocal()
    run = SchedulerRun(task="scrape", status="running", started_at=datetime.utcnow())
    db.add(run)
    db.commit()

    jobs_found = 0
    jobs_new = 0

    try:
        from backend.models.filter_config import FilterConfig
        filter_config = db.query(FilterConfig).filter(FilterConfig.is_active == True).first()

        scraped_jobs = await scraper_manager.scrape_all(filter_config)
        jobs_found = len(scraped_jobs)

        for scraped in scraped_jobs:
            # Use a savepoint so a single job failure never rolls back the others
            try:
                existing = db.query(Job).filter(Job.url == scraped.url).first()
                if existing:
                    continue

                score = filter_engine.score(scraped, filter_config)

                job = Job(
                    source=scraped.source,
                    external_id=scraped.external_id,
                    url=scraped.url,
                    title=scraped.title,
                    company=scraped.company,
                    location=scraped.location,
                    remote=scraped.remote,
                    salary_min=scraped.salary_min,
                    salary_max=scraped.salary_max,
                    description=(scraped.description or "")[:5000],
                    required_exp=scraped.required_exp,
                    skills_required=json.dumps(scraped.skills_required) if scraped.skills_required else None,
                    domain=scraped.domain,
                    visa_sponsorship=scraped.visa_sponsorship or "unknown",
                    easy_apply=scraped.easy_apply,
                    apply_url=scraped.apply_url,
                    filter_score=score,
                    priority=0,
                    status="new",
                )
                # Use nested transaction (savepoint) — failure only rolls back THIS job
                with db.begin_nested():
                    db.add(job)

                jobs_new += 1
                logger.info(f"Saved: {job.title} @ {job.company} (score={score:.0f})")

                # Enqueue for application
                try:
                    from backend.config import settings
                    if settings.auto_apply and filter_engine.passes_threshold(score):
                        from backend.services.applier.applier_manager import enqueue_job
                        job.status = "queued"
                        enqueue_job(job.id, is_telegram=False)
                except Exception as eq:
                    logger.warning(f"Enqueue error for job {job.id}: {eq}")

                # Broadcast (never let this kill the save)
                try:
                    if _broadcast_fn:
                        await _broadcast_fn({
                            "type": "new_job",
                            "job_id": job.id,
                            "title": job.title,
                            "company": job.company,
                            "score": score,
                        })
                except Exception:
                    pass

            except Exception as e:
                logger.warning(f"Skipping job '{getattr(scraped, 'title', '?')}': {e}")
                # Do NOT rollback here — savepoint handles isolation
                continue

        # Commit everything at once
        db.commit()
        logger.info(f"Scrape complete: {jobs_found} found, {jobs_new} new")

        run.status = "completed"
        run.jobs_found = jobs_found
        run.jobs_new = jobs_new
        run.ended_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        logger.error(f"Scrape worker fatal error: {e}", exc_info=True)
        try:
            db.rollback()
            run.status = "failed"
            run.error = str(e)[:500]
            run.ended_at = datetime.utcnow()
            db.commit()
        except Exception:
            pass
    finally:
        db.close()
