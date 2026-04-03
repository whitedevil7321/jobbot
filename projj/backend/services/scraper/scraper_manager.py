"""
Scraper manager — orchestrates all scrapers.
HTTP scrapers run first (fast, reliable, no browser needed).
Playwright scrapers run as fallback / for direct URL scraping when applying.
"""
import asyncio
import json
import logging
import random
from typing import List, Optional

from backend.services.scraper.base_scraper import ScrapedJob
from backend.services.scraper.http_scrapers import (
    scrape_remoteok,
    scrape_remotive,
    scrape_arbeitnow,
    scrape_indeed_rss,
    scrape_themuse,
)
from backend.services.scraper.google_jobs_scraper import scrape_google_jobs
from backend.config import settings

logger = logging.getLogger(__name__)

# Map portal name → HTTP scraper function
# LinkedIn removed — high ban risk for accounts.
# Google Jobs added — reliable public search, no account needed.
HTTP_SCRAPERS = {
    "google":    scrape_google_jobs,
    "remoteok":  scrape_remoteok,
    "remotive":  scrape_remotive,
    "arbeitnow": scrape_arbeitnow,
    "indeed":    scrape_indeed_rss,
    "themuse":   scrape_themuse,
}

# Playwright-based scrapers (used only for direct URL scraping during apply)
_playwright = None
_browser = None
_context = None


class ScraperManager:

    async def scrape_all(self, filter_config) -> List[ScrapedJob]:
        """Run all enabled HTTP scrapers and return deduplicated jobs."""
        filters = self._build_filters(filter_config)
        enabled = self._get_enabled_portals(filter_config)

        # Only run HTTP scrapers that are enabled
        http_enabled = [p for p in enabled if p in HTTP_SCRAPERS]
        random.shuffle(http_enabled)

        logger.info(f"Running scrapers: {http_enabled}")

        # Run all scrapers concurrently
        tasks = [HTTP_SCRAPERS[name](filters) for name in http_enabled]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_jobs: List[ScrapedJob] = []
        for name, result in zip(http_enabled, results):
            if isinstance(result, Exception):
                logger.error(f"Scraper '{name}' raised exception: {result}")
            elif isinstance(result, list):
                all_jobs.extend(result)

        # Deduplicate by URL
        seen: set = set()
        unique: List[ScrapedJob] = []
        for job in all_jobs:
            if job.url and job.url not in seen:
                seen.add(job.url)
                unique.append(job)

        logger.info(f"Total unique jobs scraped: {len(unique)}")
        return unique

    async def scrape_single_url(self, url: str) -> Optional[ScrapedJob]:
        """Scrape a single job URL using Playwright (for Telegram-submitted links)."""
        try:
            context = await self._get_playwright_context()
            if context is None:
                logger.warning("Playwright not available for single URL scrape")
                return _minimal_job_from_url(url)

            from backend.services.scraper.generic_scraper import GenericCareerScraper
            scraper = GenericCareerScraper(browser_context=context)
            return await scraper.scrape_url(url)
        except Exception as e:
            logger.error(f"scrape_single_url error: {e}")
            return _minimal_job_from_url(url)

    async def stop(self):
        global _playwright, _browser, _context
        try:
            if _context:
                await _context.close()
            if _browser:
                await _browser.close()
            if _playwright:
                await _playwright.stop()
        except Exception as e:
            logger.error(f"ScraperManager stop error: {e}")
        finally:
            _context = None
            _browser = None
            _playwright = None

    async def _get_playwright_context(self):
        global _playwright, _browser, _context
        if _context:
            return _context
        try:
            from playwright.async_api import async_playwright
            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=settings.headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            _context = await _browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            await _context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )
            return _context
        except Exception as e:
            logger.error(f"Playwright launch failed: {e}")
            return None

    def _build_filters(self, filter_config) -> dict:
        filters: dict = {}
        if not filter_config:
            return filters
        try:
            if filter_config.locations:
                filters["locations"] = json.loads(filter_config.locations)
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            if filter_config.domains:
                domains = json.loads(filter_config.domains)
                filters["domains"] = domains
                filters["keywords"] = " ".join(domains) if domains else ""
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            if filter_config.job_types:
                filters["job_types"] = json.loads(filter_config.job_types)
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            if filter_config.required_skills:
                filters["skills"] = json.loads(filter_config.required_skills)
        except (json.JSONDecodeError, TypeError):
            pass
        return filters

    def _get_enabled_portals(self, filter_config) -> List[str]:
        default = list(HTTP_SCRAPERS.keys())
        if not filter_config or not filter_config.portals:
            return default
        try:
            configured = json.loads(filter_config.portals)
            # Map old/legacy names to current HTTP scraper names
            remap = {
                "linkedin":    "google",    # replaced by Google Jobs
                "glassdoor":   "arbeitnow",
                "ziprecruiter":"remoteok",
                "dice":        "remotive",
                "monster":     "themuse",
            }
            mapped = [remap.get(p, p) for p in configured]
            enabled = [p for p in mapped if p in HTTP_SCRAPERS]
            return enabled if enabled else default
        except (json.JSONDecodeError, TypeError):
            return default


def _minimal_job_from_url(url: str) -> ScrapedJob:
    """Create a minimal ScrapedJob when full scraping isn't possible."""
    return ScrapedJob(
        source="telegram",
        url=url,
        title="Job from link",
        apply_url=url,
    )


scraper_manager = ScraperManager()
