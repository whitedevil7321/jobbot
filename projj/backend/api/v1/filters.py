import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.models.filter_config import FilterConfig
from backend.schemas.filter_config import FilterConfigCreate, FilterConfigUpdate, FilterConfigResponse

router = APIRouter(prefix="/filters", tags=["filters"])


@router.get("", response_model=FilterConfigResponse)
def get_active_filter(db: Session = Depends(get_db)):
    config = db.query(FilterConfig).filter(FilterConfig.is_active == True).first()
    if not config:
        raise HTTPException(404, "No active filter config found")
    return _serialize(config)


@router.post("", response_model=FilterConfigResponse)
def create_or_replace_filter(data: FilterConfigCreate, db: Session = Depends(get_db)):
    # Deactivate existing
    db.query(FilterConfig).update({"is_active": False})
    config = FilterConfig(**_deserialize(data))
    config.is_active = True
    db.add(config)
    db.commit()
    db.refresh(config)
    return _serialize(config)


@router.patch("", response_model=FilterConfigResponse)
def update_filter(data: FilterConfigUpdate, db: Session = Depends(get_db)):
    config = db.query(FilterConfig).filter(FilterConfig.is_active == True).first()
    if not config:
        raise HTTPException(404, "No active filter config found")
    update = _deserialize(data)
    for k, v in update.items():
        if v is not None:
            setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return _serialize(config)


@router.post("/test")
def test_filter(data: FilterConfigCreate, db: Session = Depends(get_db)):
    from backend.models.job import Job
    from backend.services.filters.filter_engine import filter_engine

    # Create temp config object
    config = FilterConfig(**_deserialize(data))
    jobs = db.query(Job).limit(500).all()

    passing = 0
    for job in jobs:
        from backend.services.scraper.base_scraper import ScrapedJob
        scraped = ScrapedJob(
            source=job.source,
            url=job.url,
            title=job.title,
            company=job.company,
            location=job.location,
            remote=job.remote or False,
            description=job.description,
            visa_sponsorship=job.visa_sponsorship or "unknown",
        )
        score = filter_engine.score(scraped, config)
        if filter_engine.passes_threshold(score):
            passing += 1

    return {"jobs_in_db": len(jobs), "would_pass": passing}


def _deserialize(data) -> dict:
    d = data.model_dump(exclude_unset=True)
    for field in ("locations", "job_types", "domains", "required_skills", "excluded_keywords",
                  "work_auth_required", "portals"):
        if field in d and isinstance(d[field], list):
            d[field] = json.dumps(d[field])
    return d


def _serialize(config: FilterConfig) -> dict:
    data = {c.name: getattr(config, c.name) for c in config.__table__.columns}
    for field in ("locations", "job_types", "domains", "required_skills", "excluded_keywords",
                  "work_auth_required", "portals"):
        val = data.get(field)
        if isinstance(val, str):
            try:
                data[field] = json.loads(val)
            except Exception:
                data[field] = []
    return data
