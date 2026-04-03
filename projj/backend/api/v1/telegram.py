from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.models.telegram_session import TelegramConfig

router = APIRouter(prefix="/telegram", tags=["telegram"])


class TelegramConfigRequest(BaseModel):
    bot_token: str
    chat_id: str


@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    config = db.query(TelegramConfig).filter(TelegramConfig.id == 1).first()
    if not config:
        return {"configured": False}
    return {
        "configured": True,
        "bot_token": "****" + config.bot_token[-6:] if config.bot_token else "",
        "chat_id": config.chat_id,
        "is_active": config.is_active,
    }


@router.post("/config")
async def save_config(data: TelegramConfigRequest, db: Session = Depends(get_db)):
    config = db.query(TelegramConfig).filter(TelegramConfig.id == 1).first()
    if not config:
        config = TelegramConfig(id=1)
        db.add(config)
    config.bot_token = data.bot_token
    config.chat_id = data.chat_id
    config.is_active = True
    db.commit()

    # Start bot with new token
    from backend.services.telegram.bot import start_bot
    success = await start_bot(data.bot_token)
    if not success:
        raise HTTPException(400, "Invalid bot token or could not start bot")

    return {"message": "Telegram bot configured and started"}


@router.post("/test")
async def test_bot(db: Session = Depends(get_db)):
    config = db.query(TelegramConfig).filter(TelegramConfig.id == 1).first()
    if not config:
        raise HTTPException(400, "Telegram not configured")

    from backend.services.telegram.notifier import send_message
    msg_id = await send_message("✅ JobBot test message — everything is working!")
    if msg_id:
        return {"message": "Test message sent", "message_id": msg_id}
    raise HTTPException(500, "Failed to send test message")


@router.get("/status")
def bot_status():
    from backend.services.telegram.bot import is_running
    return {"running": is_running()}
