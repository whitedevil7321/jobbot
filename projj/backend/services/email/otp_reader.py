"""
Email OTP reader — automatically reads verification/OTP codes from email
using IMAP. Supports Gmail, Outlook, Yahoo, and any IMAP-compatible provider.

Setup for Gmail:
  1. Enable 2-Factor Authentication at myaccount.google.com/security
  2. Generate an App Password at myaccount.google.com/apppasswords
  3. Set EMAIL_ADDRESS and EMAIL_PASSWORD (app password) in .env

Setup for Outlook / Hotmail:
  Set EMAIL_IMAP_HOST=imap-mail.outlook.com in .env

The reader polls the inbox every 5 seconds, looking for emails received
in the last 2 minutes that contain OTP / verification code patterns.
"""
import asyncio
import email
import imaplib
import logging
import re
import time
from email.header import decode_header
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)

# ── OTP extraction patterns ──────────────────────────────────────────────────
# Ordered from most-specific to least-specific
OTP_PATTERNS = [
    # "Your verification code is 123456"
    r"(?:verification|confirm|login|sign.?in|auth(?:entication)?|security|one.?time|access)\s+code[:\s]+([0-9]{4,8})",
    # "Code: 123456"
    r"\bcode[:\s]+([0-9]{4,8})\b",
    # "OTP: 123456"
    r"\botp[:\s]+([0-9]{4,8})\b",
    # "Token: 123456"
    r"\btoken[:\s]+([0-9]{4,8})\b",
    # "Your code is 123456"
    r"your\s+(?:code|otp|pin)\s+is[:\s]+([0-9]{4,8})",
    # "Use 123456 to verify"
    r"use\s+([0-9]{4,8})\s+to\s+(?:verify|confirm|complete)",
    # "Enter 123456"
    r"enter\s+([0-9]{4,8})",
    # Plain 6-digit code (last resort — common OTP length)
    r"\b([0-9]{6})\b",
]

# Subjects that suggest OTP emails
OTP_SUBJECT_KEYWORDS = [
    "verify", "verification", "otp", "one-time", "one time", "code",
    "confirm", "confirmation", "login", "sign in", "authentication",
    "security", "access", "token", "passcode",
]


class EmailOTPReader:
    """Read OTP codes from inbox via IMAP."""

    def __init__(self):
        self.host = settings.email_imap_host
        self.port = settings.email_imap_port
        self.username = settings.email_address
        self.password = settings.email_password
        self._lock = asyncio.Lock()

    def is_configured(self) -> bool:
        return bool(self.username and self.password)

    async def wait_for_otp(
        self,
        sender_hint: str = "",
        subject_hint: str = "",
        wait_seconds: int = None,
        since_timestamp: float = None,
    ) -> Optional[str]:
        """
        Wait up to `wait_seconds` for a new OTP email and return the code.

        Args:
            sender_hint: Partial sender address to filter (e.g. "workday", "greenhouse")
            subject_hint: Partial subject to filter
            wait_seconds: Override default wait time from settings
            since_timestamp: Unix timestamp; ignore emails before this (defaults to now-120s)

        Returns:
            OTP string (e.g. "823456") or None if not found within timeout.
        """
        if not self.is_configured():
            logger.warning("Email OTP reader not configured — skipping")
            return None

        max_wait = wait_seconds or settings.email_otp_wait_seconds
        since = since_timestamp or (time.time() - 120)  # look back 2 min by default

        logger.info(f"Waiting up to {max_wait}s for OTP email...")

        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                otp = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._fetch_otp_sync,
                    sender_hint,
                    subject_hint,
                    since,
                )
                if otp:
                    logger.info(f"OTP found: {otp}")
                    return otp
            except Exception as e:
                logger.debug(f"OTP check error: {e}")

            await asyncio.sleep(5)  # Poll every 5 seconds

        logger.warning("OTP not found within timeout")
        return None

    def _fetch_otp_sync(
        self,
        sender_hint: str,
        subject_hint: str,
        since_timestamp: float,
    ) -> Optional[str]:
        """Synchronous IMAP fetch — runs in executor thread."""
        conn = None
        try:
            conn = imaplib.IMAP4_SSL(self.host, self.port)
            conn.login(self.username, self.password)
            conn.select("INBOX")

            # Build IMAP search criteria
            # IMAP SINCE uses DD-Mon-YYYY format
            import datetime
            since_dt = datetime.datetime.fromtimestamp(since_timestamp)
            since_str = since_dt.strftime("%d-%b-%Y")

            # Search for recent unseen messages
            status, msg_nums = conn.search(None, f'(SINCE "{since_str}" UNSEEN)')
            if status != "OK" or not msg_nums[0]:
                # Also try all messages from today if UNSEEN returns nothing
                status, msg_nums = conn.search(None, f'(SINCE "{since_str}")')

            if status != "OK" or not msg_nums[0]:
                return None

            # Check newest emails first (reversed)
            ids = msg_nums[0].split()
            ids = list(reversed(ids[-20:]))  # Check last 20 emails max

            for msg_id in ids:
                try:
                    status, data = conn.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue

                    raw = data[0][1]
                    msg = email.message_from_bytes(raw)

                    # Check timestamp
                    date_str = msg.get("Date", "")
                    msg_time = 0
                    if date_str:
                        try:
                            parsed_dt = email.utils.parsedate_to_datetime(date_str)
                            msg_time = parsed_dt.timestamp() if parsed_dt else 0
                        except Exception:
                            msg_time = 0
                    if msg_time < since_timestamp:
                        continue

                    # Check sender hint
                    from_addr = msg.get("From", "").lower()
                    if sender_hint and sender_hint.lower() not in from_addr:
                        continue

                    # Decode subject
                    subject = _decode_header_str(msg.get("Subject", ""))
                    subject_lower = subject.lower()

                    # Check if this looks like an OTP email
                    is_otp_email = any(kw in subject_lower for kw in OTP_SUBJECT_KEYWORDS)
                    if subject_hint:
                        is_otp_email = is_otp_email or (subject_hint.lower() in subject_lower)

                    # Extract body text
                    body = _extract_body(msg)
                    body_lower = body.lower()

                    # If subject doesn't hint at OTP, check body for OTP keywords too
                    if not is_otp_email:
                        is_otp_email = any(kw in body_lower for kw in ["otp", "one-time code", "verification code", "your code"])

                    if not is_otp_email:
                        continue

                    # Extract OTP from body
                    otp = _extract_otp(body)
                    if otp:
                        return otp

                    # Try subject as fallback
                    otp = _extract_otp(subject)
                    if otp:
                        return otp

                except Exception as e:
                    logger.debug(f"Error parsing email {msg_id}: {e}")
                    continue

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
        except Exception as e:
            logger.error(f"Email fetch error: {e}")
        finally:
            if conn:
                try:
                    conn.logout()
                except Exception:
                    pass

        return None


def _decode_header_str(header: str) -> str:
    """Decode encoded email header."""
    try:
        parts = decode_header(header)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(str(part))
        return " ".join(decoded)
    except Exception:
        return header


def _extract_body(msg) -> str:
    """Extract plain text body from email message."""
    body_parts = []
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_parts.append(part.get_payload(decode=True).decode(charset, errors="replace"))
                    except Exception:
                        pass
                elif ctype == "text/html" and not body_parts:
                    # Fallback to HTML if no plain text
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        html = part.get_payload(decode=True).decode(charset, errors="replace")
                        # Strip HTML tags
                        body_parts.append(re.sub(r"<[^>]+>", " ", html))
                    except Exception:
                        pass
        else:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if payload:
                body_parts.append(payload.decode(charset, errors="replace"))
    except Exception as e:
        logger.debug(f"Body extract error: {e}")

    return " ".join(body_parts)


def _extract_otp(text: str) -> Optional[str]:
    """Try all OTP patterns against text, return first match."""
    text_clean = re.sub(r"\s+", " ", text)  # Normalize whitespace
    for pattern in OTP_PATTERNS:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            code = match.group(1).strip()
            # Sanity check: 4-8 digits, not all same digit (e.g. 000000)
            if 4 <= len(code) <= 8 and len(set(code)) > 1:
                return code
    return None


# Singleton instance
otp_reader = EmailOTPReader()
