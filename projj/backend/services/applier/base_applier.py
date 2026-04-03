"""Base application class with shared form-fill logic."""
import asyncio
import json
import logging
import os
import random
from dataclasses import dataclass
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
    screening_answers: Optional[dict] = None
    error: Optional[str] = None


class BaseApplier:
    def __init__(self, browser_context, profile, job):
        self.context = browser_context
        self.profile = profile
        self.job = job
        self.page: Optional[Page] = None
        self.cover_letter: str = ""
        self.screening_answers: dict = {}

    async def apply(self) -> ApplicationResult:
        raise NotImplementedError

    async def _open_page(self, url: str) -> bool:
        try:
            self.page = await self.context.new_page()
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)
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

    async def _fill_form_fields(self, form_el=None) -> dict:
        """Scan all inputs in the current page and fill them intelligently."""
        if not self.page:
            return {}
        answers = {}
        try:
            # Get all form inputs
            inputs = await self.page.query_selector_all(
                "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='file']), "
                "textarea, select"
            )
            for inp in inputs:
                try:
                    await self._fill_single_input(inp, answers)
                except Exception as e:
                    logger.debug(f"Input fill error: {e}")
        except Exception as e:
            logger.error(f"Form fill error: {e}")
        return answers

    async def _fill_single_input(self, element, answers: dict):
        tag = await element.evaluate("el => el.tagName.toLowerCase()")
        input_type = await element.get_attribute("type") or "text"
        name = await element.get_attribute("name") or ""
        placeholder = await element.get_attribute("placeholder") or ""
        label_text = await self._get_label_for(element) or name or placeholder

        if not label_text:
            return

        field_name = map_label_to_field(label_text)
        if not field_name:
            # Unknown field — ask LLM
            answer = await answer_question(self.profile, label_text)
            if answer:
                await self._set_input_value(element, tag, input_type, answer)
                answers[label_text] = answer
            return

        # Check if it's a file upload (resume)
        if input_type == "file":
            if self.profile.resume_path and os.path.exists(self.profile.resume_path):
                try:
                    await element.set_input_files(self.profile.resume_path)
                    await random_delay(0.5, 1.5)
                except Exception as e:
                    logger.debug(f"Resume upload error: {e}")
            return

        # Special fields
        if field_name == "cover_letter":
            value = self.cover_letter
        elif field_name in ("work_auth_eligible", "visa_sponsorship_needed"):
            value = await answer_yes_no(self.profile, label_text)
        else:
            value = get_profile_value(self.profile, field_name, label_text)

        if value:
            await self._set_input_value(element, tag, input_type, str(value))
            answers[label_text] = value

    async def _set_input_value(self, element, tag: str, input_type: str, value: str):
        if tag == "select":
            await self._select_option(element, value)
        elif input_type in ("checkbox", "radio"):
            # Check yes/true/yes options
            if value.lower() in ("yes", "true", "1"):
                is_checked = await element.is_checked()
                if not is_checked:
                    await element.click()
                    await random_delay(0.2, 0.5)
        elif tag in ("input", "textarea"):
            try:
                await element.scroll_into_view_if_needed()
                await random_delay(0.2, 0.5)
                await element.fill(value)
                await random_delay(0.2, 0.6)
            except Exception:
                pass

    async def _select_option(self, element, desired_value: str):
        """Select the best matching option from a dropdown."""
        try:
            options = await element.query_selector_all("option")
            opt_texts = [(await o.inner_text()).strip() for o in options]
            desired_lower = desired_value.lower()

            # Try exact match first
            for i, text in enumerate(opt_texts):
                if text.lower() == desired_lower:
                    await element.select_option(value=await options[i].get_attribute("value") or text)
                    return

            # Try contains match
            for i, text in enumerate(opt_texts):
                if desired_lower in text.lower() or text.lower() in desired_lower:
                    await element.select_option(value=await options[i].get_attribute("value") or text)
                    return

            # Special handling for yes/no
            if desired_lower in ("yes", "true"):
                for i, text in enumerate(opt_texts):
                    if text.lower() in ("yes", "true", "authorized"):
                        await element.select_option(value=await options[i].get_attribute("value") or text)
                        return
        except Exception as e:
            logger.debug(f"Select option error: {e}")

    async def _get_label_for(self, element) -> str | None:
        """Find the label text associated with an input element."""
        try:
            # Try aria-label
            aria = await element.get_attribute("aria-label")
            if aria:
                return aria.strip()

            # Try id -> label[for]
            el_id = await element.get_attribute("id")
            if el_id:
                label = await self.page.query_selector(f"label[for='{el_id}']")
                if label:
                    return (await label.inner_text()).strip()

            # Try parent label
            parent_label = await element.evaluate(
                "el => el.closest('label') ? el.closest('label').textContent : null"
            )
            if parent_label:
                return parent_label.strip()

            # Try preceding sibling label
            prev_label = await element.evaluate("""
                el => {
                    let prev = el.previousElementSibling;
                    while (prev) {
                        if (prev.tagName === 'LABEL') return prev.textContent;
                        prev = prev.previousElementSibling;
                    }
                    return null;
                }
            """)
            if prev_label:
                return prev_label.strip()

            return await element.get_attribute("placeholder")
        except Exception:
            return None

    async def _prepare_cover_letter(self) -> str:
        return await generate_cover_letter(
            self.profile,
            self.job.title or "the role",
            self.job.company or "your company",
            self.job.description or "",
        )

    async def _check_already_applied(self) -> bool:
        if not self.page:
            return False
        content = (await self.page.content()).lower()
        phrases = ["already applied", "you have applied", "application submitted", "thank you for applying"]
        return any(p in content for p in phrases)
