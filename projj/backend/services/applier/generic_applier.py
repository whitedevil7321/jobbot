"""
Universal job application handler — works on ANY career page or company website.
Handles: job portals (Greenhouse, Lever, Workday, iCIMS, SmartRecruiters, Taleo,
BambooHR, JazzHR, etc.) and direct company career pages.
"""
import asyncio
import logging
import re

from backend.services.applier.base_applier import (
    BaseApplier, ApplicationResult, ApplyStatus,
    APPLY_SELECTORS, NEXT_SUBMIT_SELECTORS, SUCCESS_PATTERNS,
)
from backend.services.applier.human_simulation import human_scroll, random_delay

logger = logging.getLogger(__name__)

# ── ATS-specific apply URL patterns ──────────────────────────────────────────
# Detects which Applicant Tracking System (ATS) the page uses
ATS_PATTERNS = {
    "greenhouse":      r"boards\.greenhouse\.io|greenhouse\.io/embed",
    "lever":           r"jobs\.lever\.co",
    "workday":         r"myworkdayjobs\.com|wd\d+\.myworkday\.com",
    "icims":           r"careers\.icims\.com|\.icims\.com",
    "smartrecruiters": r"jobs\.smartrecruiters\.com|smartrecruiters\.com/jobs",
    "ashby":           r"jobs\.ashbyhq\.com",
    "bamboohr":        r"\.bamboohr\.com/jobs",
    "jobvite":         r"jobs\.jobvite\.com",
    "taleo":           r"\.taleo\.net",
    "successfactors":  r"\.successfactors\.(com|eu)",
    "jazz":            r"app\.jazz\.co",
    "rippling":        r"ats\.rippling\.com",
    "dover":           r"app\.dover\.com",
    "indeed":          r"indeed\.com/apply",
    "linkedin":        r"linkedin\.com/jobs/apply",
}


def _detect_ats(url: str) -> str:
    """Return the ATS name for a given URL, or 'generic'."""
    url_lower = url.lower()
    for ats, pattern in ATS_PATTERNS.items():
        if re.search(pattern, url_lower):
            return ats
    return "generic"


class GenericApplier(BaseApplier):

    async def apply(self) -> ApplicationResult:
        url = self.job.apply_url or self.job.url
        if not url:
            return ApplicationResult(status=ApplyStatus.FAILED, error="No URL for job")

        ats = _detect_ats(url)
        logger.info(f"Applying to job {self.job.id} via {ats}: {url}")

        if not await self._open_page(url):
            return ApplicationResult(status=ApplyStatus.FAILED, error="Could not open page")

        try:
            # ── Bot / CAPTCHA wall check ───────────────────────────────────
            if await self._check_bot_wall():
                logger.warning(f"Bot protection detected for job {self.job.id}: {self.page.url}")
                return ApplicationResult(
                    status=ApplyStatus.FAILED,
                    error="Bot/Cloudflare protection — cannot apply automatically",
                )

            # ── Check if already applied ──────────────────────────────────
            if await self._check_already_applied():
                return ApplicationResult(status=ApplyStatus.ALREADY_APPLIED)

            # ── Generate cover letter in background ───────────────────────
            self.cover_letter = await self._prepare_cover_letter()

            # ── Handle ATS-specific login prompts ─────────────────────────
            await self._handle_login_prompt()

            # ── Find and click Apply button ───────────────────────────────
            apply_clicked = await self._click_apply_button()
            if not apply_clicked:
                logger.info("No apply button found — treating page as direct application form")

            # ── If page still has no form inputs (listing page), try once more ──
            # Some job boards (e.g. arbeitnow) have two layers: clicking "Apply"
            # on the listing goes to the company's ATS which may itself need an
            # "Apply" click before the form appears.
            if not await self._page_has_form_inputs():
                second_click = await self._click_apply_button()
                if second_click:
                    logger.info("Found second-level apply button — clicked it")
                    await self._handle_login_prompt()

            await random_delay(2, 4)

            # ── Handle multi-step form (up to 15 steps) ───────────────────
            prev_url = self.page.url
            for step in range(15):
                logger.info(f"Step {step + 1} for job {self.job.id}")

                await human_scroll(self.page, "down", 400)
                await random_delay(0.5, 1.0)

                # Check for success first
                if await self._check_success():
                    screenshot = await self._take_screenshot("_success")
                    return ApplicationResult(
                        status=ApplyStatus.SUBMITTED,
                        screenshot_path=screenshot,
                        cover_letter_used=self.cover_letter,
                        screening_answers=self.screening_answers,
                    )

                # Fill all visible form fields
                answers = await self._fill_form_fields()
                if answers:
                    self.screening_answers.update(answers)

                # Upload resume
                await self._handle_resume_upload()

                await random_delay(1, 2)

                # Check for success again (some forms submit on fill)
                if await self._check_success():
                    screenshot = await self._take_screenshot("_success")
                    return ApplicationResult(
                        status=ApplyStatus.SUBMITTED,
                        screenshot_path=screenshot,
                        cover_letter_used=self.cover_letter,
                        screening_answers=self.screening_answers,
                    )

                # Try to proceed (Next / Submit)
                proceeded = await self._click_next_or_submit()

                if not proceeded:
                    screenshot = await self._take_screenshot("_stuck")
                    return ApplicationResult(
                        status=ApplyStatus.STUCK,
                        stuck_reason="Could not find Next/Submit button",
                        screenshot_path=screenshot,
                        screening_answers=self.screening_answers,
                    )

                await random_delay(2, 4)
                await self._dismiss_popups()

                # Check success after submit
                if await self._check_success():
                    screenshot = await self._take_screenshot("_success")
                    return ApplicationResult(
                        status=ApplyStatus.SUBMITTED,
                        screenshot_path=screenshot,
                        cover_letter_used=self.cover_letter,
                        screening_answers=self.screening_answers,
                    )

                # Detect if we're on the same page (stuck in a loop)
                current_url = self.page.url
                if current_url == prev_url:
                    # Check if there are required fields we missed
                    unfilled = await self._find_unfilled_required()
                    if unfilled:
                        logger.warning(f"Required fields unfilled: {unfilled}")
                        # Try to fill them
                        for field_el, label in unfilled:
                            try:
                                await self._fill_single_input(field_el, self.screening_answers)
                            except Exception:
                                pass
                        # Try submit again
                        await self._click_next_or_submit()
                        await random_delay(2, 3)
                        if await self._check_success():
                            screenshot = await self._take_screenshot("_success")
                            return ApplicationResult(
                                status=ApplyStatus.SUBMITTED,
                                screenshot_path=screenshot,
                                cover_letter_used=self.cover_letter,
                                screening_answers=self.screening_answers,
                            )
                        # Still stuck
                        screenshot = await self._take_screenshot("_stuck")
                        return ApplicationResult(
                            status=ApplyStatus.STUCK,
                            stuck_reason=f"Required fields could not be filled: {', '.join(l for _, l in unfilled[:3])}",
                            screenshot_path=screenshot,
                            screening_answers=self.screening_answers,
                        )

                prev_url = current_url

            screenshot = await self._take_screenshot("_timeout")
            return ApplicationResult(
                status=ApplyStatus.STUCK,
                stuck_reason="Maximum form steps (15) reached without submission",
                screenshot_path=screenshot,
                screening_answers=self.screening_answers,
            )

        except Exception as e:
            logger.error(f"GenericApplier error for job {self.job.id}: {e}", exc_info=True)
            screenshot = await self._take_screenshot("_error")
            return ApplicationResult(
                status=ApplyStatus.FAILED,
                error=str(e),
                screenshot_path=screenshot,
            )
        finally:
            await self._close_page()

    async def _handle_login_prompt(self):
        """
        Some ATSs ask you to sign in / create account before applying.
        We skip sign-in prompts and look for 'Apply without account' / 'Guest' links.
        """
        if not self.page:
            return
        guest_selectors = [
            "a:has-text('Apply without signing in')",
            "a:has-text('Continue as guest')",
            "button:has-text('Continue as guest')",
            "a:has-text('Apply as guest')",
            "button:has-text('Apply without account')",
            "a:has-text('Skip sign in')",
            "button:has-text('Skip')",
            "a:has-text('Continue without')",
        ]
        for sel in guest_selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    await el.click()
                    await random_delay(1.5, 3)
                    logger.info("Clicked guest/no-account option")
                    return
            except Exception:
                continue

    async def _find_unfilled_required(self) -> list:
        """Find required form fields that are still empty."""
        unfilled = []
        try:
            required = await self.page.query_selector_all(
                "input[required]:not([type='hidden']):not([type='submit']):not([type='file']), "
                "textarea[required], select[required], "
                "[aria-required='true']"
            )
            for el in required:
                try:
                    if not await el.is_visible():
                        continue
                    tag = await el.evaluate("e => e.tagName.toLowerCase()")
                    val = await el.evaluate("e => e.value")
                    if not val or not val.strip():
                        label = await self._get_label_for(el) or "Unknown field"
                        unfilled.append((el, label))
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Required field check error: {e}")
        return unfilled
