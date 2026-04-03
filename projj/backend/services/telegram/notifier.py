"""Send notifications to user via Telegram."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_bot_app = None


def set_bot(app):
    global _bot_app
    _bot_app = app


async def send_message(text: str, with_buttons: bool = False, application_id: Optional[int] = None) -> Optional[int]:
    """Send a message to the configured chat. Returns message_id if successful."""
    if not _bot_app:
        logger.warning("Telegram bot not configured")
        return None

    from backend.database import SessionLocal
    from backend.models.telegram_session import TelegramConfig
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    db = SessionLocal()
    try:
        config = db.query(TelegramConfig).filter(TelegramConfig.id == 1).first()
        if not config or not config.is_active:
            return None

        chat_id = config.chat_id
        kwargs = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

        if with_buttons and application_id:
            keyboard = [
                [
                    InlineKeyboardButton("⏭ Skip", callback_data=f"decision:{application_id}:skip"),
                    InlineKeyboardButton("🔄 Retry", callback_data=f"decision:{application_id}:retry"),
                    InlineKeyboardButton("✋ Manual", callback_data=f"decision:{application_id}:manual"),
                ]
            ]
            kwargs["reply_markup"] = InlineKeyboardMarkup(keyboard)

        msg = await _bot_app.bot.send_message(**kwargs)
        return msg.message_id
    except Exception as e:
        logger.error(f"Telegram send_message error: {e}")
        return None
    finally:
        db.close()


async def notify(text: str) -> None:
    await send_message(text)
