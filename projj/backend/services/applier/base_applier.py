"""Base application class with shared form-fill logic, OTP handling, and smart answers."""
import asyncio
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from playwright.async_api import Page

from backend.services.applier.form_parser import map_label_to_field, get_profile_value
from backend.services.applier.human_simulation import human_type, human_click, human_scroll, random_delay
from backend.services.llm.cover_letter import generate_cover_letter, answer_question, answer_yes_no

logger = logging.getLogger(__name__)

SCREENSHOTS_DIR = "data/screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# ── OTP field detection patterns ─────────────────────────────────────────────
OTP_FIELD_PATTERNS = [
    r"otp", r"one.?time", r"verification\s*code", r"verify\s*code",
    r"auth.*code", r"security\s*code", r"confirm.*code", r"access\s*code",
    r"passcode", r"pin\s*code", r"2fa", r"two.?factor",
]

# ── Selector sets for common page actions ────────────────────────────────────
APPLY_SELECTORS = [
    "a:has-text('Apply Now')", "button:has-text('Apply Now')",
    "a:has-text('Apply for this job')", "button:has-text('Apply for this job')",
    "a:has-text('Easy Apply')", "button:has-text('Easy Apply')",
    "a:has-text('Apply')", "button:has-text('Apply')",
    "a[class*='apply']", "button[class*='apply']",
    "a[id*='apply']", "button[id*='apply']",
    "a[href*='apply']",
    "[data-automation*='apply']",
    "[aria-label*='apply' i]",
]

NEXT_SUBMIT_SELECTORS = [
    "button[type='submit']", "input[type='submit']",
    "button:has-text('Submit Application')", "button:has-text('Submit')",
    "button:has-text('Send Application')", "button:has-text('Send')",
    "button:has-text('Next')", "button:has-text('Continue')",
    "button:has-text('Proceed')", "button:has-text('Next Step')",
    "a:has-text('Submit')", "a:has-text('Next')",
    "[data-automation*='submit']", "[aria-label*='next' i]",
    "[aria-label*='submit' i]",
]

SUCCESS_PATTERNS = [
    "application submitted", "thank you for applying", "we received your application",
    "application received", "successfully applied", "your application has been",
    "application complete", "you've applied", "you have applied",
    "application was submitted", "submitted successfully",
]

ALREADY_APPLIED_PATTERNS = [
    "already applied", "you have applied", "application submitted",
    "previously applied", "you've already applied",
]

# Popup/modal selectors that might block forms
POPUP_CLOSE_SELECTORS = [
    "button[aria-label*='close' i]", "button[aria-label*='dismiss' i]",
    ".modal-close", ".popup-close", "[class*='modal'] button:has-text('×')",
    "button:has-text('No thanks')", "button:has-text('Not now')",
    "button:has-text('Skip')", "button:has-text('Close')",
    "button:has-text('Dismiss')",
]


class ApplyStatus(str, Enum):
    SUBMITTED = "submitted"
    STUCK = "stuck"
    SKIPPED = "skipped"
    FAILED = "failed"
    ALREADY_APPLIED = "already_applied"


@dataclass
class ApplicationResult:
    status: ApplyStatus
    stuck_reason: Optional[str] = None
    stuck_field: Optional[str] = None
    screenshot_path: Optional[str] = None
    cover_letter_used: Optional[str] = None
    screening_answers: Optional[dict] = field(default_factory=dict)
    error: Optional[str] = None


class BaseApplier:
    def __init__(self, browser_context, profile, job):
        self.context = browser_context
        self.profile = profile
        self.job = job
        self.page: Optional[Page] = None
        self.cover_letter: str = ""
        self.screening_answers: dict = {}
        self._otp_since: float = time.time()

    async def apply(self) -> ApplicationResult:
        raise NotImplementedError

    # ── Page lifecycle ────────────────────────────────────────────────────────

    async def _open_page(self, url: str) -> bool:
        try:
            self.page = await self.context.new_page()
            # Record time before loading so OTP reader looks at emails from now on
            self._otp_since = time.time()
            await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await random_delay(2, 4)
            await self._dismiss_popups()
            return True
        except Exception as e:
            logger.error(f"Failed to open page {url}: {e}")
            return False

    async def _close_page(self):
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass
            self.page = None

    async def _take_screenshot(self, suffix: str = "") -> str:
        if not self.page:
            return ""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"{SCREENSHOTS_DIR}/{self.job.id}_{ts}{suffix}.png"
            await self.page.screenshot(path=fname, full_page=True)
            return fname
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return ""

    # ── Popup handling ────────────────────────────────────────────────────────

    async def _dismiss_popups(self):
        """Dismiss any blocking popups / cookie banners / modals."""
        if not self.page:
            return
        for sel in POPUP_CLOSE_SELECTORS:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    await el.click()
                    await random_delay(0.5, 1.0)
            except Exception:
                continue

        # Cookie consent banners
        for text in ["Accept All", "Accept Cookies", "Allow all cookies", "I Accept"]:
            try:
                el = await self.page.query_selector(f"button:has-text('{text}')")
                if el and await el.is_visible():
                    await el.click()
                    await random_delay(0.5, 1.0)
                    break
            except Exception:
                continue

    # ── Apply button ──────────────────────────────────────────────────────────

    async def _click_apply_button(self) -> bool:
        if not self.page:
            return False
        for sel in APPLY_SELECTORS:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    await el.scroll_into_view_if_needed()
                    await random_delay(0.5, 1.2)
                    await el.click()
                    await random_delay(2, 4)
                    await self._dismiss_popups()
                    return True
            except Exception:
                continue
        return False

    # ── Resume upload ─────────────────────────────────────────────────────────

    async def _handle_resume_upload(self):
        if not self.profile.resume_path:
            return
        if not os.path.exists(self.profile.resume_path):
            logger.warning(f"Resume file not found: {self.profile.resume_path}")
            return
        try:
            file_inputs = await self.page.query_selector_all("input[type='file']")
            for fi in file_inputs:
                try:
                    if await fi.is_visible():
                        await fi.set_input_files(self.profile.resume_path)
                        await random_delay(1.0, 2.5)
                        logger.info("Resume uploaded")
                        break
                except Exception:
                    # Try even if not visible — some sites hide the input
                    try:
                        await fi.set_input_files(self.profile.resume_path)
                        await random_delay(1.0, 2.0)
                        break
                    except Exception:
                        continue
        except Exception as e:
            logger.debug(f"Resume upload error: {e}")

    # ── OTP handling ──────────────────────────────────────────────────────────

    def _is_otp_field(self, label_text: str, name: str, placeholder: str) -> bool:
        """Return True if this input looks like an OTP/verification code field."""
        combined = f"{label_text} {name} {placeholder}".lower()
        return any(re.search(p, combined) for p in OTP_FIELD_PATTERNS)

    async def _handle_otp_field(self, element, label_text: str) -> bool:
        """
        Auto-fill an OTP field by reading the verification email.
        Returns True if OTP was successfully filled.
        """
        from backend.services.email.otp_reader import otp_reader

        if not otp_reader.is_configured():
            logger.warning("OTP field detected but email reader not configured")
            return False

        logger.info(f"OTP field detected: '{label_text}' — waiting for email code...")

        # Try to detect the sender domain from the page URL
        sender_hint = ""
        try:
            current_url = self.page.url
            from urllib.parse import urlparse
            domain = urlparse(current_url).netloc
            sender_hint = domain.replace("www.", "").split(".")[0]
        except Exception:
            pass

        otp = await otp_reader.wait_for_otp(
            sender_hint=sender_hint,
            since_timestamp=self._otp_since,
        )

        if otp:
            try:
                await element.scroll_into_view_if_needed()
                await element.click()
                await random_delay(0.3, 0.7)
                await element.fill(otp)
                await random_delay(0.5, 1.0)
                logger.info(f"OTP filled: {otp}")
                return True
            except Exception as e:
                logger.error(f"OTP fill error: {e}")
                return False
        else:
            logger.warning("Could not obtain OTP from email")
            return False

    # ── Form filling ──────────────────────────────────────────────────────────

    async def _fill_form_fields(self, form_el=None) -> dict:
        """Scan all visible inputs on the page and fill them intelligently."""
        if not self.page:
            return {}
        answers = {}
        try:
            inputs = await self.page.query_selector_all(
                "input:not([type='hidden']):not([type='submit'])"
                ":not([type='button']):not([type='file']):not([type='image']), "
                "textarea, select"
            )
            for inp in inputs:
                try:
                    if not await inp.is_visible():
                        continue
                    await self._fill_single_input(inp, answers)
                except Exception as e:
                    logger.debug(f"Input fill error: {e}")
        except Exception as e:
            logger.error(f"Form fill error: {e}")
        return answers

    async def _fill_single_input(self, element, answers: dict):
        tag = await element.evaluate("el => el.tagName.toLowerCase()")
        input_type = (await element.get_attribute("type") or "text").lower()
        name = await element.get_attribute("name") or ""
        placeholder = await element.get_attribute("placeholder") or ""
        autocomplete = await element.get_attribute("autocomplete") or ""
        label_text = await self._get_label_for(element) or name or placeholder or autocomplete

        if not label_text:
            return

        # ── OTP fields ─────────────────────────────────────────────────────
        if self._is_otp_field(label_text, name, placeholder):
            await self._handle_otp_field(element, label_text)
            answers[label_text] = "[OTP auto-filled from email]"
            return

        # ── File upload (resume) ────────────────────────────────────────────
        if input_type == "file":
            if self.profile.resume_path and os.path.exists(self.profile.resume_path):
                try:
                    await element.set_input_files(self.profile.resume_path)
                    await random_delay(0.5, 1.5)
                    answers["resume"] = self.profile.resume_path
                except Exception:
                    pass
            return

        # ── Rule-based field matching ───────────────────────────────────────
        field_name = map_label_to_field(label_text)

        if field_name == "cover_letter":
            value = self.cover_letter
        elif field_name in ("work_auth_eligible", "visa_sponsorship_needed"):
            value = await answer_yes_no(self.profile, label_text)
        elif field_name:
            value = get_profile_value(self.profile, field_name, label_text)
        else:
            # ── Unknown field → LLM / smart_answers fallback ───────────────
            try:
                from backend.services.llm.smart_answers import smart_answer_question
                value = await smart_answer_question(self.profile, label_text, self.job)
            except Exception:
                value = await answer_question(self.profile, label_text)

        if value:
            await self._set_input_value(element, tag, input_type, str(value))
            answers[label_text] = value

    async def _set_input_value(self, element, tag: str, input_type: str, value: str):
        """Set the value of a form field with human-like behavior."""
        try:
            if tag == "select":
                await self._select_option(element, value)
            elif input_type == "checkbox":
                if value.lower() in ("yes", "true", "1", "on"):
                    is_checked = await element.is_checked()
                    if not is_checked:
                        await element.click()
                        await random_delay(0.2, 0.5)
            elif input_type == "radio":
                # Find radio group and pick best match
                await self._handle_radio_group(element, value)
            elif tag in ("input", "textarea"):
                await element.scroll_into_view_if_needed()
                await random_delay(0.1, 0.4)
                # Clear first then fill
                await element.click()
                await element.fill("")
                await random_delay(0.1, 0.3)
                await element.fill(value)
                await random_delay(0.2, 0.5)
        except Exception as e:
            logger.debug(f"Set input value error: {e}")

    async def _handle_radio_group(self, element, desired_value: str):
        """Select the best matching radio button in a group."""
        try:
            name = await element.get_attribute("name")
            if not name:
                return
            radios = await self.page.query_selector_all(f"input[type='radio'][name='{name}']")
            desired_lower = desired_value.lower()

            for radio in radios:
                radio_val = (await radio.get_attribute("value") or "").lower()
                radio_label = await self._get_label_for(radio) or ""
                radio_label_lower = radio_label.lower()

                # Try to match "yes/no" or boolean radios
                if desired_lower in ("yes", "true") and radio_val in ("yes", "true", "1", "y"):
                    await radio.click()
                    return
                if desired_lower in ("no", "false") and radio_val in ("no", "false", "0", "n"):
                    await radio.click()
                    return

                # Try value/label match
                if desired_lower in radio_val or desired_lower in radio_label_lower:
                    await radio.click()
                    return

        except Exception as e:
            logger.debug(f"Radio group error: {e}")

    async def _select_option(self, element, desired_value: str):
        """Select the best-matching option in a <select> dropdown."""
        try:
            options = await element.query_selector_all("option")
            opt_texts = [(await o.inner_text()).strip() for o in options]
            opt_values = [(await o.get_attribute("value") or "").strip() for o in options]
            desired_lower = desired_value.lower()

            # 1. Exact value match
            for i, v in enumerate(opt_values):
                if v.lower() == desired_lower:
                    await element.select_option(value=v)
                    return

            # 2. Exact text match
            for i, text in enumerate(opt_texts):
                if text.lower() == desired_lower:
                    await element.select_option(value=opt_values[i] or text)
                    return

            # 3. Contains match
            for i, text in enumerate(opt_texts):
                if desired_lower in text.lower() or text.lower() in desired_lower:
                    await element.select_option(value=opt_values[i] or text)
                    return

            # 4. Yes/No special handling
            if desired_lower in ("yes", "true", "authorized", "citizen"):
                for i, text in enumerate(opt_texts):
                    if text.lower() in ("yes", "true", "authorized", "us citizen", "citizen"):
                        await element.select_option(value=opt_values[i] or text)
                        return

            # 5. Prefer not to say / N/A for demographics
            if "prefer" in desired_lower or "not" in desired_lower:
                for i, text in enumerate(opt_texts):
                    if "prefer" in text.lower() or "decline" in text.lower():
                        await element.select_option(value=opt_values[i] or text)
                        return

        except Exception as e:
            logger.debug(f"Select option error: {e}")

    # ── Label detection ───────────────────────────────────────────────────────

    async def _get_label_for(self, element) -> Optional[str]:
        """Find the label text associated with an input element."""
        try:
            # 1. aria-label
            aria = await element.get_attribute("aria-label")
            if aria and aria.strip():
                return aria.strip()

            # 2. aria-labelledby
            labelledby = await element.get_attribute("aria-labelledby")
            if labelledby:
                label_el = await self.page.query_selector(f"#{labelledby}")
                if label_el:
                    text = (await label_el.inner_text()).strip()
                    if text:
                        return text

            # 3. id → label[for="id"]
            el_id = await element.get_attribute("id")
            if el_id:
                label = await self.page.query_selector(f"label[for='{el_id}']")
                if label:
                    text = (await label.inner_text()).strip()
                    if text:
                        return text

            # 4. Ancestor label element
            parent_label = await element.evaluate("""
                el => {
                    let node = el;
                    while (node && node !== document.body) {
                        if (node.tagName === 'LABEL') return node.textContent;
                        node = node.parentElement;
                    }
                    return null;
                }
            """)
            if parent_label and parent_label.strip():
                return parent_label.strip()

            # 5. Preceding sibling label
            prev_label = await element.evaluate("""
                el => {
                    let prev = el.previousElementSibling;
                    while (prev) {
                        if (prev.tagName === 'LABEL' || prev.tagName === 'SPAN' || prev.tagName === 'P') {
                            const t = prev.textContent.trim();
                            if (t.length > 0 && t.length < 100) return t;
                        }
                        prev = prev.previousElementSibling;
                    }
                    return null;
                }
            """)
            if prev_label and prev_label.strip():
                return prev_label.strip()

            # 6. placeholder / name / autocomplete
            placeholder = await element.get_attribute("placeholder")
            if placeholder and placeholder.strip():
                return placeholder.strip()

            name = await element.get_attribute("name")
            if name:
                return name.replace("_", " ").replace("-", " ").strip()

        except Exception:
            pass
        return None

    # ── Next / Submit ─────────────────────────────────────────────────────────

    async def _click_next_or_submit(self) -> bool:
        if not self.page:
            return False
        for sel in NEXT_SUBMIT_SELECTORS:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible() and await el.is_enabled():
                    await el.scroll_into_view_if_needed()
                    await random_delay(0.5, 1.5)
                    await el.click()
                    await random_delay(2, 4)
                    await self._dismiss_popups()
                    return True
            except Exception:
                continue
        return False

    # ── Success / already-applied checks ─────────────────────────────────────

    async def _check_success(self) -> bool:
        if not self.page:
            return False
        try:
            content = (await self.page.content()).lower()
            url = self.page.url.lower()
            return (
                any(p in content for p in SUCCESS_PATTERNS) or
                "success" in url or "thank" in url or "confirmation" in url
            )
        except Exception:
            return False

    async def _check_already_applied(self) -> bool:
        if not self.page:
            return False
        try:
            content = (await self.page.content()).lower()
            return any(p in content for p in ALREADY_APPLIED_PATTERNS)
        except Exception:
            return False

    # ── Cover letter ──────────────────────────────────────────────────────────

    async def _prepare_cover_letter(self) -> str:
        try:
            return await generate_cover_letter(
                self.profile,
                self.job.title or "the role",
                self.job.company or "your company",
                self.job.description or "",
            )
        except Exception as e:
            logger.warning(f"Cover letter generation failed: {e}")
            # Minimal fallback
            name = self.profile.full_name or "Applicant"
            title = self.job.title or "this position"
            company = self.job.company or "your company"
            return (
                f"Dear Hiring Manager,\n\n"
                f"I am writing to express my interest in the {title} position at {company}. "
                f"With my background and skills, I am confident I would be a great fit.\n\n"
                f"Best regards,\n{name}"
            )
