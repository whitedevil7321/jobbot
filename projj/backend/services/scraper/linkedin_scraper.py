import asyncio
import logging
import json
from typing import List
from urllib.parse import urlencode, quote
from backend.services.scraper.base_scraper import BaseScraper, ScrapedJob

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    name = "linkedin"
    BASE_URL = "https://www.linkedin.com/jobs/search/?"

    async def scrape(self, filters: dict) -> List[ScrapedJob]:
        jobs = []
        try:
            page = await self.context.new_page()
            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })

            locations = filters.get("locations", ["United States"])
            keywords = filters.get("keywords", filters.get("domains", ["software engineer"]))
            if isinstance(keywords, list):
                keywords = " OR ".join(keywords) if keywords else "software engineer"

            for location in locations[:3]:
                params = {
                    "keywords": keywords,
                    "location": location,
                    "f_TPR": "r3600",  # last hour
                    "sortBy": "DD",
                }
                if filters.get("job_types"):
                    job_types = filters["job_types"]
                    if job_types:
                        jt = job_types[0]
                        type_map = {"full-time": "F", "part-time": "P", "contract": "C", "internship": "I"}
                        if jt in type_map:
                            params["f_JT"] = type_map[jt]

                url = self.BASE_URL + urlencode(params)
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await self.human_delay(2, 4)

                    # Scroll to load more jobs
                    for _ in range(3):
                        await page.evaluate("window.scrollBy(0, 800)")
                        await asyncio.sleep(0.8)

                    # Extract job cards
                    job_cards = await page.query_selector_all(".job-search-card, .jobs-search__results-list li")
                    logger.info(f"LinkedIn: found {len(job_cards)} cards for '{keywords}' in '{location}'")

                    for card in job_cards[:20]:
                        try:
                            job = await self._parse_card(card, page)
                            if job:
                                jobs.append(job)
                        except Exception as e:
                            logger.debug(f"LinkedIn card parse error: {e}")

                    await self.human_delay(3, 6)
                except Exception as e:
                    logger.error(f"LinkedIn scrape error for {location}: {e}")

            await page.close()
        except Exception as e:
            logger.error(f"LinkedIn scraper fatal error: {e}")

        return jobs

    async def _parse_card(self, card, page) -> ScrapedJob | None:
        try:
            title_el = await card.query_selector("h3.base-search-card__title, .job-card-list__title")
            company_el = await card.query_selector("h4.base-search-card__subtitle, .job-card-container__company-name")
            location_el = await card.query_selector(".job-search-card__location, .job-card-container__metadata-item")
            link_el = await card.query_selector("a.base-card__full-link, a.job-card-list__title")

            title = (await title_el.inner_text()).strip() if title_el else None
            company = (await company_el.inner_text()).strip() if company_el else None
            location = (await location_el.inner_text()).strip() if location_el else None
            href = await link_el.get_attribute("href") if link_el else None

            if not title or not href:
                return None

            # Clean URL
            url = href.split("?")[0] if "?" in href else href
            if not url.startswith("http"):
                url = "https://www.linkedin.com" + url

            job_id = url.split("/jobs/view/")[-1].rstrip("/") if "/jobs/view/" in url else None

            remote = "remote" in (location or "").lower()

            return ScrapedJob(
                source="linkedin",
                url=url,
                title=title,
                company=company,
                location=location,
                remote=remote,
                easy_apply=False,
                apply_url=url,
                external_id=job_id,
            )
        except Exception as e:
            logger.debug(f"LinkedIn _parse_card error: {e}")
            return None
