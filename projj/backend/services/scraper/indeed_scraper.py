import asyncio
import logging
import re
from typing import List
from urllib.parse import urlencode, quote_plus
from backend.services.scraper.base_scraper import BaseScraper, ScrapedJob

logger = logging.getLogger(__name__)


class IndeedScraper(BaseScraper):
    name = "indeed"
    BASE_URL = "https://www.indeed.com/jobs?"

    async def scrape(self, filters: dict) -> List[ScrapedJob]:
        jobs = []
        try:
            page = await self.context.new_page()
            locations = filters.get("locations", ["United States"])
            keywords = filters.get("keywords", "software engineer")
            if isinstance(keywords, list):
                keywords = " ".join(keywords) if keywords else "software engineer"

            for location in locations[:2]:
                params = {
                    "q": keywords,
                    "l": location,
                    "sort": "date",
                    "fromage": "1",  # last day
                }
                url = self.BASE_URL + urlencode(params)
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await self.human_delay(2, 4)

                    for _ in range(2):
                        await page.evaluate("window.scrollBy(0, 600)")
                        await asyncio.sleep(0.7)

                    job_cards = await page.query_selector_all(".job_seen_beacon, .jobsearch-ResultsList li.css-1m4cuuf")
                    logger.info(f"Indeed: found {len(job_cards)} cards")

                    for card in job_cards[:20]:
                        try:
                            job = await self._parse_card(card)
                            if job:
                                jobs.append(job)
                        except Exception as e:
                            logger.debug(f"Indeed card error: {e}")

                    await self.human_delay(3, 5)
                except Exception as e:
                    logger.error(f"Indeed scrape error: {e}")

            await page.close()
        except Exception as e:
            logger.error(f"Indeed scraper fatal: {e}")
        return jobs

    async def _parse_card(self, card) -> ScrapedJob | None:
        try:
            title_el = await card.query_selector("h2.jobTitle span[id], h2.jobTitle a")
            company_el = await card.query_selector("[data-testid='company-name'], .companyName")
            location_el = await card.query_selector("[data-testid='text-location'], .companyLocation")
            salary_el = await card.query_selector("[data-testid='attribute_snippet_testid'], .salary-snippet")
            link_el = await card.query_selector("h2.jobTitle a, a.jcs-JobTitle")

            title = (await title_el.inner_text()).strip() if title_el else None
            company = (await company_el.inner_text()).strip() if company_el else None
            location = (await location_el.inner_text()).strip() if location_el else None
            salary_text = (await salary_el.inner_text()).strip() if salary_el else None
            href = await link_el.get_attribute("href") if link_el else None

            if not title or not href:
                return None

            url = href if href.startswith("http") else "https://www.indeed.com" + href
            job_id_match = re.search(r"jk=([a-z0-9]+)", url)
            job_id = job_id_match.group(1) if job_id_match else None

            salary_min, salary_max = self.parse_salary(salary_text or "")
            remote = "remote" in (location or "").lower()

            return ScrapedJob(
                source="indeed",
                url=url,
                title=title,
                company=company,
                location=location,
                remote=remote,
                salary_min=salary_min,
                salary_max=salary_max,
                apply_url=url,
                external_id=job_id,
            )
        except Exception as e:
            logger.debug(f"Indeed _parse_card error: {e}")
            return None
