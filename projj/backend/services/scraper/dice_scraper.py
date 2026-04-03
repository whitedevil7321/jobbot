import asyncio
import logging
from typing import List
from urllib.parse import urlencode
from backend.services.scraper.base_scraper import BaseScraper, ScrapedJob

logger = logging.getLogger(__name__)


class DiceScraper(BaseScraper):
    name = "dice"

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
                    "q": keywords,
                    "location": location,
                    "datePosted": "ONE",  # last day
                    "page": "1",
                }
                url = "https://www.dice.com/jobs?" + urlencode(params)
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await self.human_delay(2, 4)

                    for _ in range(2):
                        await page.evaluate("window.scrollBy(0, 700)")
                        await asyncio.sleep(0.8)

                    job_cards = await page.query_selector_all(
                        "dhi-search-card, .card-title-link, [data-cy='card-title-link']"
                    )
                    logger.info(f"Dice: found {len(job_cards)} cards")

                    for card in job_cards[:20]:
                        try:
                            job = await self._parse_card(card, page)
                            if job:
                                jobs.append(job)
                        except Exception as e:
                            logger.debug(f"Dice card error: {e}")

                    await self.human_delay(3, 6)
                except Exception as e:
                    logger.error(f"Dice scrape error: {e}")

            await page.close()
        except Exception as e:
            logger.error(f"Dice scraper fatal: {e}")
        return jobs

    async def _parse_card(self, card, page) -> ScrapedJob | None:
        try:
            title_el = await card.query_selector("a.card-title-link, h5 a, [data-cy='card-title-link']")
            company_el = await card.query_selector("a.company-name-link, [data-cy='search-result-company-name']")
            location_el = await card.query_selector("span.search-result-location, [data-cy='search-result-location']")

            title = (await title_el.inner_text()).strip() if title_el else None
            company = (await company_el.inner_text()).strip() if company_el else None
            location = (await location_el.inner_text()).strip() if location_el else None
            href = await title_el.get_attribute("href") if title_el else None

            if not title or not href:
                return None

            url = href if href.startswith("http") else "https://www.dice.com" + href
            remote = "remote" in (location or "").lower()

            return ScrapedJob(
                source="dice",
                url=url,
                title=title,
                company=company,
                location=location,
                remote=remote,
                apply_url=url,
            )
        except Exception as e:
            logger.debug(f"Dice _parse_card error: {e}")
            return None
