"""Initialize database tables and seed default data."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.database import engine, Base
import backend.models  # noqa: F401 - ensures all models are registered


def init_db():
    Base.metadata.create_all(bind=engine)
    print("[✓] Database tables created.")

    # Seed default filter config
    from backend.database import SessionLocal
    from backend.models.filter_config import FilterConfig
    import json

    db = SessionLocal()
    try:
        existing = db.query(FilterConfig).filter_by(name="default").first()
        if not existing:
            default_filter = FilterConfig(
                name="default",
                is_active=True,
                locations=json.dumps(["Remote", "United States"]),
                min_years_exp=0,
                max_years_exp=10,
                job_types=json.dumps(["full-time"]),
                # Default keywords for tech/ML jobs — update via the Filters page
                domains=json.dumps(["Software Engineer", "Python", "Data", "AI", "Machine Learning"]),
                required_skills=json.dumps([]),
                excluded_keywords=json.dumps([]),
                visa_sponsorship_filter="any",
                portals=json.dumps(["google", "indeed", "remoteok", "remotive", "arbeitnow", "themuse"]),
            )
            db.add(default_filter)
            db.commit()
            print("[✓] Default filter config seeded.")
        else:
            print("[i] Default filter config already exists.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
