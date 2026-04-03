"""Generic job application handler for any career page."""
import asyncio
import logging
import re
from backend.services.applier.base_applier import BaseApplier, ApplicationResult, ApplyStatus
from backend.services.applier.human_simulation import human_scroll, random_delay, human_click

logger = logging.getLogger(__name__)

APPLY_BUTTON_PATTERNS = [
    "text=Apply Now", "text=Apply", "text=Easy Apply", "text=Apply for this job",
    "text=Submit Application", "text=Apply to this job", "text=Apply for Job",
    "button[contains(@class,'apply')]",
]

SUBMIT_BUTTON_PATTERNS = [
    "text=Submit", "text=Submit Application", "text=Send Application",
    "button[type='submit']", "input[type='submit']",
    "text=Next", "text=Continue",
]

SUCCESS_PATTERNS = [
    "application submitted", "thank you for applying", "we received your application",
    "application received", "successfully applied", "your application has been",
]


class GenericApplier(BaseApplier):
    async def apply(self) -> ApplicationResult:
        url = self.job.apply_url or self.job.url
        if not await self._open_page(url):
            return ApplicationResult(status=ApplyStatus.FAILED, error="Could not open page")

        try:
            if await self._check_already_applied():
                return ApplicationResult(status=ApplyStatus.ALREADY_APPLIED)

            # Prepare cover letter in background
            self.cover_letter = await self._prepare_cover_letter()

            # Find and click apply button
            apply_clicked = await self._click_apply_button()
            if not apply_clicked:
                # Some pages are the application form directly
                logger.info(f"No apply button found at {url}, treating page as form")

            await random_delay(2, 4)

            # Handle multi-step form (up to 10 steps)
            for step in range(10):
                logger.info(f"Filling form step {step + 1} for job {self.job.id}")

                # Fill all visible form fields
                answers = await self._fill_form_fields()
                if answers:
                    self.screening_answers.update(answers)

                # Upload resume if file input present
                await self._handle_resume_upload()

                await random_delay(1, 2)

                # Check for success
                if await self._check_success():
                    screenshot = await self._take_screenshot("_success")
                    return ApplicationResult(
                        status=ApplyStatus.SUBMITTED,
                        screenshot_path=screenshot,
                        cover_letter_used=self.cover_letter,
                        screening_answers=self.screening_answers,
                    )

                # Try to proceed to next step
                proceeded = await self._click_next_or_submit()
                if not proceeded:
                    # Stuck
                    screenshot = await self._take_screenshot("_stuck")
                    return ApplicationResult(
                        status=ApplyStatus.STUCK,
                        stuck_reason="Could not proceed to next step or submit",
                        screenshot_path=screenshot,
                        screening_answers=self.screening_answers,
                    )

                await random_delay(2, 4)

                # Check for success after submit
                if await self._check_success():
                    screenshot = await self._take_screenshot("_success")
                    return ApplicationResult(
                        status=ApplyStatus.SUBMITTED,
                        screenshot_path=screenshot,
                        cover_letter_used=self.cover_letter,
                        screening_answers=self.screening_answers,
                    )

            screenshot = await self._take_screenshot("_timeout")
            return ApplicationResult(
                status=ApplyStatus.STUCK,
                stuck_reason="Maximum form steps reached",
                screenshot_path=screenshot,
            )

        except Exception as e:
            logger.error(f"GenericApplier error for job {self.job.id}: {e}")
            screenshot = await self._take_screenshot("_error")
            return ApplicationResult(
                status=ApplyStatus.FAILED,
                error=str(e),
                screenshot_path=screenshot,
            )
        finally:
            await self._close_page()

    async def _click_apply_button(self) -> bool:
        if not self.page:
            return False
        apply_selectors = [
            "a:has-text('Apply Now')", "button:has-text('Apply Now')",
            "a:has-text('Apply')", "button:has-text('Apply')",
            "a:has-text('Easy Apply')", "button:has-text('Easy Apply')",
            "a[class*='apply']", "button[class*='apply']",
            "a[href*='apply']",
        ]
        for sel in apply_selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    await el.scroll_into_view_if_needed()
                    await random_delay(0.5, 1.0)
                    await el.click()
                    await random_delay(1.5, 3)
                    return True
            except Exception:
                continue
        return False

    async def _handle_resume_upload(self):
        if not self.profile.resume_path:
            return
        import os
        if not os.path.exists(self.profile.resume_path):
            return
        try:
            file_inputs = await self.page.query_selector_all("input[type='file']")
            for fi in file_inputs:
                if await fi.is_visible():
                    await fi.set_input_files(self.profile.resume_path)
                    await random_delay(0.8, 2.0)
                    break
        except Exception as e:
            logger.debug(f"Resume upload error: {e}")

    async def _click_next_or_submit(self) -> bool:
        if not self.page:
            return False
        button_selectors = [
            "button[type='submit']", "input[type='submit']",
            "button:has-text('Submit')", "button:has-text('Next')",
            "button:has-text('Continue')", "button:has-text('Proceed')",
            "a:has-text('Submit')", "a:has-text('Next')",
        ]
        for sel in button_selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    await el.scroll_into_view_if_needed()
                    await random_delay(0.5, 1.5)
                    await el.click()
                    await random_delay(2, 4)
                    return True
            except Exception:
                continue
        return False

    async def _check_success(self) -> bool:
        if not self.page:
            return False
        try:
            content = (await self.page.content()).lower()
            return any(p in content for p in SUCCESS_PATTERNS)
        except Exception:
            return False
