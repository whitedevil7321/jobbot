import asyncio
import logging
from typing import List
from urllib.parse import urlencode
from backend.services.scraper.base_scraper import BaseScraper, ScrapedJob

logger = logging.getLogger(__name__)


class ZipRecruiterScraper(BaseScraper):
    name = "ziprecruiter"

    async def scrape(self, filters: dict) -> List[ScrapedJob]:
        jobs = []
        try:
            page = await self.context.new_page()
            keywords = filters.get("keywords", "software engineer")
            if isinstance(keywords, list):
                keywords = " ".join(keywords) if keywords else "software engineer"
            locations = filters.get("locations", ["United States"])

            for location in locations[:2]:
                params = {
                    "search": keywords,
                    "location": location,
                    "days": "1",
                }
                url = "https://www.ziprecruiter.com/jobs-search?" + urlencode(params)
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await self.human_delay(2, 4)

                    for _ in range(2):
                        await page.evaluate("window.scrollBy(0, 600)")
                        await asyncio.sleep(0.7)

                    job_cards = await page.query_selector_all("article.job_result, div[data-testid='job-card']")
                    logger.info(f"ZipRecruiter: found {len(job_cards)} cards")

                    for card in job_cards[:20]:
                        try:
                            job = await self._parse_card(card)
                            if job:
                                jobs.append(job)
                        except Exception as e:
                            logger.debug(f"ZipRecruiter card error: {e}")

                    await self.human_delay(3, 5)
                except Exception as e:
                    logger.error(f"ZipRecruiter scrape error: {e}")

            await page.close()
        except Exception as e:
            logger.error(f"ZipRecruiter scraper fatal: {e}")
        return jobs

    async def _parse_card(self, card) -> ScrapedJob | None:
        try:
            title_el = await card.query_selector("h2.jobTitle, .job_title, [data-testid='job-title']")
            company_el = await card.query_selector(".company_name, [data-testid='job-employer']")
            location_el = await card.query_selector(".location, [data-testid='job-location']")
            salary_el = await card.query_selector(".compensation, [data-testid='job-salary']")
            link_el = await card.query_selector("a.job_result_link, a[data-testid='job-link']")

            title = (await title_el.inner_text()).strip() if title_el else None
            company = (await company_el.inner_text()).strip() if company_el else None
            location = (await location_el.inner_text()).strip() if location_el else None
            salary_text = (await salary_el.inner_text()).strip() if salary_el else None
            href = await link_el.get_attribute("href") if link_el else None

            if not title or not href:
                return None

            url = href if href.startswith("http") else "https://www.ziprecruiter.com" + href
            salary_min, salary_max = self.parse_salary(salary_text or "")
            remote = "remote" in (location or "").lower()

            return ScrapedJob(
                source="ziprecruiter",
                url=url,
                title=title,
                company=company,
                location=location,
                remote=remote,
                salary_min=salary_min,
                salary_max=salary_max,
                apply_url=url,
            )
        except Exception as e:
            logger.debug(f"ZipRecruiter _parse_card error: {e}")
            return None
