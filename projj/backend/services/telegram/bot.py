"""Telegram bot setup and lifecycle."""
import logging
from typing import Optional

from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from backend.services.telegram.handlers import (
    start_handler, help_handler, status_handler,
    message_handler, callback_handler, pause_handler, resume_handler,
)
from backend.services.telegram import notifier

logger = logging.getLogger(__name__)

_app: Optional[Application] = None


async def start_bot(token: str) -> bool:
    global _app
    if _app:
        await stop_bot()

    try:
        _app = Application.builder().token(token).build()

        # Register handlers
        _app.add_handler(CommandHandler("start", start_handler))
        _app.add_handler(CommandHandler("help", help_handler))
        _app.add_handler(CommandHandler("status", status_handler))
        _app.add_handler(CommandHandler("pause", pause_handler))
        _app.add_handler(CommandHandler("resume", resume_handler))
        _app.add_handler(CallbackQueryHandler(callback_handler))
        _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

        # Set notifier
        notifier.set_bot(_app)

        # Register notifier with applier manager
        from backend.services.applier import applier_manager
        applier_manager.set_notifier(_make_notify_fn())

        await _app.initialize()
        await _app.start()
        await _app.updater.start_polling(drop_pending_updates=True)

        logger.info("Telegram bot started successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
        _app = None
        return False


async def stop_bot():
    global _app
    if _app:
        try:
            await _app.updater.stop()
            await _app.stop()
            await _app.shutdown()
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
        finally:
            _app = None


def is_running() -> bool:
    return _app is not None


def _make_notify_fn():
    async def notify(text: str, with_buttons: bool = False, application_id: Optional[int] = None) -> Optional[int]:
        return await notifier.send_message(text, with_buttons=with_buttons, application_id=application_id)
    return notify


async def try_start_from_db():
    """Try to start the bot using stored config from DB."""
    from backend.database import SessionLocal
    from backend.models.telegram_session import TelegramConfig

    db = SessionLocal()
    try:
        config = db.query(TelegramConfig).filter(TelegramConfig.id == 1).first()
        if config and config.is_active and config.bot_token:
            await start_bot(config.bot_token)
    except Exception as e:
        logger.error(f"try_start_from_db error: {e}")
    finally:
        db.close()
