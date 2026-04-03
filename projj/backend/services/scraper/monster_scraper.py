import asyncio
import logging
from typing import List
from urllib.parse import urlencode
from backend.services.scraper.base_scraper import BaseScraper, ScrapedJob

logger = logging.getLogger(__name__)


class MonsterScraper(BaseScraper):
    name = "monster"

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
                    "where": location,
                    "tm": "1",  # 1 day
                }
                url = "https://www.monster.com/jobs/search?" + urlencode(params)
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await self.human_delay(2, 4)

                    for _ in range(2):
                        await page.evaluate("window.scrollBy(0, 700)")
                        await asyncio.sleep(0.7)

                    job_cards = await page.query_selector_all(
                        ".job-search-resultsstyle__CardWrapper-sc-1irgb5m-0, [data-testid='jobCard']"
                    )
                    logger.info(f"Monster: found {len(job_cards)} cards")

                    for card in job_cards[:15]:
                        try:
                            job = await self._parse_card(card)
                            if job:
                                jobs.append(job)
                        except Exception as e:
                            logger.debug(f"Monster card error: {e}")

                    await self.human_delay(3, 5)
                except Exception as e:
                    logger.error(f"Monster scrape error: {e}")

            await page.close()
        except Exception as e:
            logger.error(f"Monster scraper fatal: {e}")
        return jobs

    async def _parse_card(self, card) -> ScrapedJob | None:
        try:
            title_el = await card.query_selector("h2 a, [data-testid='jobTitle']")
            company_el = await card.query_selector(".company, [data-testid='company']")
            location_el = await card.query_selector(".location, [data-testid='location']")
            link_el = await card.query_selector("a[href*='/job-openings/']")

            title = (await title_el.inner_text()).strip() if title_el else None
            company = (await company_el.inner_text()).strip() if company_el else None
            location = (await location_el.inner_text()).strip() if location_el else None
            href = await link_el.get_attribute("href") if link_el else (
                await title_el.get_attribute("href") if title_el else None
            )

            if not title or not href:
                return None

            url = href if href.startswith("http") else "https://www.monster.com" + href
            remote = "remote" in (location or "").lower()

            return ScrapedJob(
                source="monster",
                url=url,
                title=title,
                company=company,
                location=location,
                remote=remote,
                apply_url=url,
            )
        except Exception as e:
            logger.debug(f"Monster _parse_card error: {e}")
            return None
