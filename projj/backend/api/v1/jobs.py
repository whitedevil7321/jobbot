import json
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.models.job import Job, JobApplication
from backend.schemas.job import JobResponse, JobManualSubmit, ApplicationResponse, DecisionRequest, ApplicationStats
from backend.services.applier.applier_manager import enqueue_job

router = APIRouter(tags=["jobs"])


@router.get("/jobs")
def list_jobs(
    status: Optional[str] = None,
    source: Optional[str] = None,
    min_score: float = 0.0,
    page: int = 1,
    limit: int = 50,
    sort_by: str = "scraped_at",
    db: Session = Depends(get_db),
):
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    if source:
        q = q.filter(Job.source == source)
    if min_score > 0:
        q = q.filter(Job.filter_score >= min_score)

    order_map = {
        "scraped_at": Job.scraped_at.desc(),
        "filter_score": Job.filter_score.desc(),
        "priority": Job.priority.asc(),
        "title": Job.title.asc(),
    }
    q = q.order_by(order_map.get(sort_by, Job.scraped_at.desc()))

    total = q.count()
    jobs = q.offset((page - 1) * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "jobs": [_serialize_job(j) for j in jobs],
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return _serialize_job(job)


@router.post("/jobs/manual")
async def submit_manual_job(data: JobManualSubmit, db: Session = Depends(get_db)):
    existing = db.query(Job).filter(Job.url == data.url).first()
    if existing:
        if existing.status != "applied":
            existing.priority = 1
            existing.status = "queued"
            db.commit()
            enqueue_job(existing.id, is_telegram=True)
        return {"message": "Job queued", "job_id": existing.id}

    from backend.services.scraper.scraper_manager import scraper_manager
    scraped = await scraper_manager.scrape_single_url(data.url)

    job = Job(
        source="manual",
        url=data.url,
        title=data.title or (scraped.title if scraped else "Manual Job"),
        company=data.company or (scraped.company if scraped else None),
        location=scraped.location if scraped else None,
        remote=scraped.remote if scraped else False,
        description=scraped.description if scraped else None,
        priority=1,
        status="queued",
        apply_url=data.url,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    enqueue_job(job.id, is_telegram=True)
    return {"message": "Job queued with priority", "job_id": job.id}


@router.post("/jobs/{job_id}/apply")
async def apply_to_job(job_id: int, db: Session = Depends(get_db)):
    """Enqueue a single job for immediate application."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status in ("applied", "applying"):
        return {"message": "Already applied or applying", "job_id": job_id}
    job.status = "queued"
    job.priority = 1
    db.commit()
    enqueue_job(job_id, is_telegram=True)
    return {"message": "Job queued for immediate application", "job_id": job_id}


@router.post("/jobs/apply-all")
async def apply_all_jobs(db: Session = Depends(get_db)):
    """Enqueue all new/stuck jobs for application."""
    jobs = db.query(Job).filter(
        Job.status.in_(["new", "stuck"])
    ).order_by(Job.filter_score.desc()).all()

    queued = 0
    for job in jobs:
        job.status = "queued"
        enqueue_job(job.id, is_telegram=False)
        queued += 1

    db.commit()
    return {"message": f"Queued {queued} jobs for application", "count": queued}


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    db.delete(job)
    db.commit()
    return {"message": "Job deleted"}


@router.patch("/jobs/{job_id}/priority")
def prioritize_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    job.priority = 1
    if job.status == "new":
        job.status = "queued"
        enqueue_job(job.id, is_telegram=True)
    db.commit()
    return {"message": "Job prioritized"}


@router.get("/applications")
def list_applications(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(JobApplication)
    if status:
        q = q.filter(JobApplication.status == status)
    q = q.order_by(JobApplication.created_at.desc())
    total = q.count()
    apps = q.offset((page - 1) * limit).limit(limit).all()
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "applications": [_serialize_app(a) for a in apps],
    }


@router.get("/applications/stats")
def application_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    rows = db.query(JobApplication.status, func.count()).group_by(JobApplication.status).all()
    counts = {r[0]: r[1] for r in rows}
    total = sum(counts.values())
    return ApplicationStats(
        total=total,
        pending=counts.get("pending", 0),
        in_progress=counts.get("in_progress", 0),
        submitted=counts.get("submitted", 0),
        stuck=counts.get("stuck", 0),
        skipped=counts.get("skipped", 0),
        failed=counts.get("failed", 0),
    )


@router.get("/applications/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db)):
    app = db.query(JobApplication).filter(JobApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    return _serialize_app(app)


@router.patch("/applications/{app_id}/decision")
def resolve_application(app_id: int, data: DecisionRequest, db: Session = Depends(get_db)):
    application = db.query(JobApplication).filter(JobApplication.id == app_id).first()
    if not application:
        raise HTTPException(404, "Application not found")

    action = data.action
    job = application.job

    if action == "skip":
        application.status = "skipped"
        application.user_response = "skip"
        if job:
            job.status = "skipped"
    elif action == "retry":
        application.status = "pending"
        application.user_response = "retry"
        if job:
            job.status = "queued"
            enqueue_job(job.id, is_telegram=True)
    elif action == "manual":
        application.status = "skipped"
        application.user_response = "manual"
        if job:
            job.status = "skipped"

    db.commit()
    return {"message": f"Action '{action}' applied"}


def _serialize_job(job: Job) -> dict:
    data = {c.name: getattr(job, c.name) for c in job.__table__.columns}
    if data.get("skills_required") and isinstance(data["skills_required"], str):
        try:
            data["skills_required"] = json.loads(data["skills_required"])
        except Exception:
            data["skills_required"] = []
    return data


def _serialize_app(app: JobApplication) -> dict:
    data = {c.name: getattr(app, c.name) for c in app.__table__.columns}
    if data.get("screening_answers") and isinstance(data["screening_answers"], str):
        try:
            data["screening_answers"] = json.loads(data["screening_answers"])
        except Exception:
            data["screening_answers"] = {}
    return data
