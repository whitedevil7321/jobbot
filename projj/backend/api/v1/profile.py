import json
import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.models.user_profile import UserProfile
from backend.schemas.profile import UserProfileCreate, UserProfileResponse

router = APIRouter(prefix="/profile", tags=["profile"])

RESUME_DIR = "data/resumes"
os.makedirs(RESUME_DIR, exist_ok=True)


@router.get("", response_model=UserProfileResponse)
def get_profile(db: Session = Depends(get_db)):
    profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
    if not profile:
        profile = UserProfile(id=1)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return _serialize(profile)


@router.post("", response_model=UserProfileResponse)
def upsert_profile(data: UserProfileCreate, db: Session = Depends(get_db)):
    profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
    if not profile:
        profile = UserProfile(id=1)
        db.add(profile)

    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if k in ("target_roles", "target_domains", "skills") and isinstance(v, list):
            setattr(profile, k, json.dumps(v))
        else:
            setattr(profile, k, v)

    db.commit()
    db.refresh(profile)
    return _serialize(profile)


@router.post("/resume")
async def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    allowed = {".pdf", ".docx", ".doc"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(400, "Only PDF and DOCX files are allowed")

    path = os.path.join(RESUME_DIR, f"resume{ext}")
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    # Extract text
    resume_text = _extract_text(path, ext)

    profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
    if not profile:
        profile = UserProfile(id=1)
        db.add(profile)
    profile.resume_path = path
    profile.resume_text = resume_text
    db.commit()

    return {"message": "Resume uploaded", "path": path, "text_extracted": bool(resume_text)}


def _extract_text(path: str, ext: str) -> str:
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif ext in (".docx", ".doc"):
            from docx import Document
            doc = Document(path)
            return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        pass
    return ""


def _serialize(profile: UserProfile) -> dict:
    data = {c.name: getattr(profile, c.name) for c in profile.__table__.columns}
    for field in ("target_roles", "target_domains", "skills"):
        val = data.get(field)
        if isinstance(val, str):
            try:
                data[field] = json.loads(val)
            except Exception:
                data[field] = []
    return data
