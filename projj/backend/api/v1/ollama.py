from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json

from backend.services.llm.ollama_client import ollama
from backend.config import settings

router = APIRouter(prefix="/ollama", tags=["ollama"])


class ModelRequest(BaseModel):
    model_name: str


class ActiveModelRequest(BaseModel):
    model_name: str


class GenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = None


@router.get("/status")
async def ollama_status():
    running = await ollama.is_running()
    return {"running": running, "host": settings.ollama_host, "active_model": settings.ollama_model}


@router.get("/models")
async def list_models():
    models = await ollama.list_models()
    return {"models": models, "active": settings.ollama_model}


@router.post("/models/pull")
async def pull_model(data: ModelRequest):
    async def stream():
        async for chunk in ollama.pull_model(data.model_name):
            yield json.dumps(chunk) + "\n"
    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.patch("/models/active")
async def set_active_model(data: ActiveModelRequest):
    models = await ollama.list_models()
    if data.model_name not in models:
        raise HTTPException(400, f"Model '{data.model_name}' not found. Pull it first.")
    settings.ollama_model = data.model_name
    ollama.model = data.model_name
    return {"message": f"Active model set to {data.model_name}"}


@router.post("/generate/cover-letter")
async def test_cover_letter(data: GenerateRequest):
    from backend.database import SessionLocal
    from backend.models.user_profile import UserProfile
    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
        if not profile:
            raise HTTPException(400, "No profile found")
        from backend.services.llm.cover_letter import generate_cover_letter
        result = await generate_cover_letter(profile, "Software Engineer", "Test Company", data.prompt)
        return {"result": result}
    finally:
        db.close()


@router.post("/generate/answer")
async def test_answer(data: GenerateRequest):
    from backend.database import SessionLocal
    from backend.models.user_profile import UserProfile
    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
        if not profile:
            raise HTTPException(400, "No profile found")
        from backend.services.llm.cover_letter import answer_question
        result = await answer_question(profile, data.prompt)
        return {"result": result}
    finally:
        db.close()
