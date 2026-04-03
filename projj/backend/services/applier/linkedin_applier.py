"""LinkedIn Easy Apply handler."""
import asyncio
import logging
from backend.services.applier.base_applier import BaseApplier, ApplicationResult, ApplyStatus
from backend.services.applier.human_simulation import random_delay, human_scroll

logger = logging.getLogger(__name__)


class LinkedInApplier(BaseApplier):
    async def apply(self) -> ApplicationResult:
        url = self.job.url
        if not await self._open_page(url):
            return ApplicationResult(status=ApplyStatus.FAILED, error="Could not open LinkedIn page")

        try:
            if await self._check_already_applied():
                return ApplicationResult(status=ApplyStatus.ALREADY_APPLIED)

            self.cover_letter = await self._prepare_cover_letter()

            # Click Easy Apply button
            easy_apply_clicked = await self._click_easy_apply()
            if not easy_apply_clicked:
                # Fall back to external apply
                external = await self._click_external_apply()
                if not external:
                    return ApplicationResult(
                        status=ApplyStatus.STUCK,
                        stuck_reason="Could not find apply button on LinkedIn",
                        screenshot_path=await self._take_screenshot("_no_apply_btn"),
                    )
                # If external apply, use generic applier on new page
                return ApplicationResult(
                    status=ApplyStatus.STUCK,
                    stuck_reason="External apply link - redirected to company page",
                )

            await random_delay(2, 3)

            # Handle multi-step Easy Apply modal
            for step in range(8):
                logger.info(f"LinkedIn Easy Apply step {step + 1}")

                # Fill form fields in modal
                modal = await self.page.query_selector(".jobs-easy-apply-modal, [role='dialog']")
                if modal:
                    inputs = await modal.query_selector_all(
                        "input:not([type='hidden']):not([type='submit']), textarea, select"
                    )
                    for inp in inputs:
                        try:
                            await self._fill_single_input(inp, self.screening_answers)
                        except Exception as e:
                            logger.debug(f"LinkedIn input fill error: {e}")

                await random_delay(1, 2)

                # Check for review/submit page
                submit_btn = await self.page.query_selector(
                    "button[aria-label='Submit application'], button:has-text('Submit application')"
                )
                if submit_btn and await submit_btn.is_visible():
                    await submit_btn.scroll_into_view_if_needed()
                    await random_delay(0.5, 1.5)
                    await submit_btn.click()
                    await random_delay(2, 3)

                    # Dismiss confirmation dialog if present
                    dismiss = await self.page.query_selector("button:has-text('Done'), button:has-text('Close')")
                    if dismiss:
                        await dismiss.click()

                    screenshot = await self._take_screenshot("_submitted")
                    return ApplicationResult(
                        status=ApplyStatus.SUBMITTED,
                        screenshot_path=screenshot,
                        cover_letter_used=self.cover_letter,
                        screening_answers=self.screening_answers,
                    )

                # Click Next
                next_btn = await self.page.query_selector(
                    "button[aria-label='Continue to next step'], "
                    "button:has-text('Next'), button:has-text('Review')"
                )
                if next_btn and await next_btn.is_visible():
                    await next_btn.scroll_into_view_if_needed()
                    await random_delay(0.5, 1.0)
                    await next_btn.click()
                    await random_delay(1.5, 3)
                else:
                    # Stuck
                    screenshot = await self._take_screenshot("_stuck")
                    return ApplicationResult(
                        status=ApplyStatus.STUCK,
                        stuck_reason="Could not proceed to next step in LinkedIn Easy Apply",
                        screenshot_path=screenshot,
                    )

            screenshot = await self._take_screenshot("_max_steps")
            return ApplicationResult(
                status=ApplyStatus.STUCK,
                stuck_reason="Maximum Easy Apply steps reached",
                screenshot_path=screenshot,
            )

        except Exception as e:
            logger.error(f"LinkedInApplier error: {e}")
            screenshot = await self._take_screenshot("_error")
            return ApplicationResult(status=ApplyStatus.FAILED, error=str(e), screenshot_path=screenshot)
        finally:
            await self._close_page()

    async def _click_easy_apply(self) -> bool:
        selectors = [
            "button.jobs-apply-button:has-text('Easy Apply')",
            "button[aria-label*='Easy Apply']",
            ".jobs-apply-button--top-card",
        ]
        for sel in selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    await el.scroll_into_view_if_needed()
                    await random_delay(0.5, 1.5)
                    await el.click()
                    return True
            except Exception:
                continue
        return False

    async def _click_external_apply(self) -> bool:
        selectors = [
            "button.jobs-apply-button:not(:has-text('Easy Apply'))",
            "a[href*='apply']",
        ]
        for sel in selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    await el.click()
                    return True
            except Exception:
                continue
        return False
