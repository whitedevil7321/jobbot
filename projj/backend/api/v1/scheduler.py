from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from backend.services.scheduler.job_scheduler import get_scheduler_status, trigger_scrape_now
from backend.config import settings

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class SchedulerConfig(BaseModel):
    scrape_interval_minutes: Optional[int] = None
    auto_apply: Optional[bool] = None


@router.get("/status")
def scheduler_status():
    return get_scheduler_status()


@router.post("/scrape/trigger")
async def trigger_scrape():
    await trigger_scrape_now()
    return {"message": "Scrape triggered"}


@router.post("/apply/trigger")
async def trigger_apply():
    from backend.database import SessionLocal
    from backend.models.job import Job
    from backend.services.applier.applier_manager import enqueue_job

    db = SessionLocal()
    try:
        queued_jobs = db.query(Job).filter(Job.status == "queued").limit(20).all()
        for job in queued_jobs:
            enqueue_job(job.id, is_telegram=job.priority == 1)
        return {"message": f"Enqueued {len(queued_jobs)} jobs for application"}
    finally:
        db.close()


@router.patch("/config")
def update_scheduler_config(data: SchedulerConfig):
    if data.scrape_interval_minutes is not None:
        settings.scrape_interval_minutes = data.scrape_interval_minutes
    if data.auto_apply is not None:
        settings.auto_apply = data.auto_apply
    return {"message": "Scheduler config updated", "config": {
        "scrape_interval_minutes": settings.scrape_interval_minutes,
        "auto_apply": settings.auto_apply,
    }}


@router.get("/logs")
def scheduler_logs():
    from backend.database import SessionLocal
    from backend.models.scheduler import SchedulerRun
    db = SessionLocal()
    try:
        runs = db.query(SchedulerRun).order_by(SchedulerRun.started_at.desc()).limit(50).all()
        return [
            {
                "id": r.id, "task": r.task, "status": r.status,
                "jobs_found": r.jobs_found, "jobs_new": r.jobs_new,
                "error": r.error,
                "started_at": str(r.started_at), "ended_at": str(r.ended_at),
            }
            for r in runs
        ]
    finally:
        db.close()
