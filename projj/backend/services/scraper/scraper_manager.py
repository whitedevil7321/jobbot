import asyncio
import json
import logging
import random
from typing import List
from playwright.async_api import async_playwright, BrowserContext

from backend.services.scraper.base_scraper import ScrapedJob
from backend.services.scraper.linkedin_scraper import LinkedInScraper
from backend.services.scraper.indeed_scraper import IndeedScraper
from backend.services.scraper.glassdoor_scraper import GlassdoorScraper
from backend.services.scraper.ziprecruiter_scraper import ZipRecruiterScraper
from backend.services.scraper.dice_scraper import DiceScraper
from backend.services.scraper.monster_scraper import MonsterScraper
from backend.services.scraper.generic_scraper import GenericCareerScraper
from backend.config import settings

logger = logging.getLogger(__name__)

SCRAPER_CLASSES = {
    "linkedin": LinkedInScraper,
    "indeed": IndeedScraper,
    "glassdoor": GlassdoorScraper,
    "ziprecruiter": ZipRecruiterScraper,
    "dice": DiceScraper,
    "monster": MonsterScraper,
}


class ScraperManager:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080",
            ],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        # Stealth: hide webdriver flag
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)
        logger.info("ScraperManager browser started")

    async def stop(self):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("ScraperManager browser stopped")

    async def scrape_all(self, filter_config) -> List[ScrapedJob]:
        if not self._context:
            await self.start()

        filters = self._build_filters(filter_config)
        enabled_portals = self._get_enabled_portals(filter_config)

        # Randomize order for anti-detection
        random.shuffle(enabled_portals)

        all_jobs = []
        for portal_name in enabled_portals:
            cls = SCRAPER_CLASSES.get(portal_name)
            if not cls:
                continue
            try:
                scraper = cls(browser_context=self._context)
                jobs = await scraper.scrape(filters)
                logger.info(f"{portal_name}: scraped {len(jobs)} jobs")
                all_jobs.extend(jobs)
                # Delay between portals
                await asyncio.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.error(f"Scraper {portal_name} failed: {e}")

        # Deduplicate by URL
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                unique_jobs.append(job)

        logger.info(f"Total unique jobs scraped: {len(unique_jobs)}")
        return unique_jobs

    async def scrape_single_url(self, url: str) -> ScrapedJob | None:
        if not self._context:
            await self.start()
        scraper = GenericCareerScraper(browser_context=self._context)
        return await scraper.scrape_url(url)

    def _build_filters(self, filter_config) -> dict:
        if not filter_config:
            return {}
        filters = {}
        if filter_config.locations:
            filters["locations"] = json.loads(filter_config.locations)
        if filter_config.domains:
            filters["keywords"] = json.loads(filter_config.domains)
        if filter_config.job_types:
            filters["job_types"] = json.loads(filter_config.job_types)
        return filters

    def _get_enabled_portals(self, filter_config) -> list[str]:
        if filter_config and filter_config.portals:
            return json.loads(filter_config.portals)
        return list(SCRAPER_CLASSES.keys())


scraper_manager = ScraperManager()
