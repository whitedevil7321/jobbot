"""
Email configuration API — save/test IMAP settings for OTP auto-reading.
"""
import asyncio
import imaplib
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.config import settings

router = APIRouter(tags=["email"])
logger = logging.getLogger(__name__)


class EmailConfigRequest(BaseModel):
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    email_address: str
    email_password: str
    otp_wait_seconds: int = 60


class EmailConfigResponse(BaseModel):
    imap_host: str
    imap_port: int
    email_address: Optional[str]
    otp_wait_seconds: int
    configured: bool


@router.get("/email-config")
async def get_email_config() -> EmailConfigResponse:
    """Get current email OTP configuration (password masked)."""
    return EmailConfigResponse(
        imap_host=settings.email_imap_host,
        imap_port=settings.email_imap_port,
        email_address=settings.email_address,
        otp_wait_seconds=settings.email_otp_wait_seconds,
        configured=bool(settings.email_address and settings.email_password),
    )


@router.post("/email-config/test")
async def test_email_config(data: EmailConfigRequest):
    """
    Test the IMAP connection with provided credentials.
    Returns success/failure message.
    """
    def _test_sync():
        conn = imaplib.IMAP4_SSL(data.imap_host, data.imap_port)
        conn.login(data.email_address, data.email_password)
        status, folders = conn.list()
        conn.logout()
        return status == "OK"

    try:
        ok = await asyncio.get_event_loop().run_in_executor(None, _test_sync)
        if ok:
            return {"success": True, "message": "Email connection successful! OTP reading is ready."}
        else:
            return {"success": False, "message": "Connected but could not list folders."}
    except imaplib.IMAP4.error as e:
        raise HTTPException(400, f"IMAP authentication failed: {e}")
    except ConnectionRefusedError:
        raise HTTPException(400, f"Could not connect to {data.imap_host}:{data.imap_port}")
    except Exception as e:
        raise HTTPException(400, f"Connection error: {e}")


@router.post("/email-config/test-otp")
async def test_otp_read():
    """Test OTP reading — look for any OTP/verification emails in the last 5 minutes."""
    from backend.services.email.otp_reader import otp_reader
    import time

    if not otp_reader.is_configured():
        raise HTTPException(400, "Email not configured. Set EMAIL_ADDRESS and EMAIL_PASSWORD in .env")

    try:
        otp = await otp_reader.wait_for_otp(
            since_timestamp=time.time() - 300,  # Last 5 minutes
            wait_seconds=10,                      # Don't wait long for test
        )
        if otp:
            return {"found": True, "otp": otp, "message": f"Found OTP code: {otp}"}
        else:
            return {"found": False, "otp": None, "message": "No OTP email found in last 5 minutes. This is normal if no verification email was received."}
    except Exception as e:
        raise HTTPException(500, f"OTP read error: {e}")
