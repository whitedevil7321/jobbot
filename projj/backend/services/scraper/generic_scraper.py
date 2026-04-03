"""Generic career page scraper — handles arbitrary company job pages."""
import asyncio
import logging
import re
from typing import List
from urllib.parse import urlparse
from backend.services.scraper.base_scraper import BaseScraper, ScrapedJob

logger = logging.getLogger(__name__)


class GenericCareerScraper(BaseScraper):
    name = "generic"

    async def scrape_url(self, url: str) -> ScrapedJob | None:
        """Scrape a single job URL directly (used for Telegram-submitted links)."""
        try:
            page = await self.context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.human_delay(1.5, 3)

            # Extract title
            title = await self._extract_title(page)
            company = await self._extract_company(page, url)
            location = await self._extract_location(page)
            description = await self._extract_description(page)

            await page.close()

            if not title:
                return None

            domain = urlparse(url).netloc.replace("www.", "")
            source = self._guess_source(url)

            return ScrapedJob(
                source=source,
                url=url,
                title=title,
                company=company or domain,
                location=location,
                remote="remote" in (location or "").lower() or "remote" in description.lower() if description else False,
                description=description,
                apply_url=url,
            )
        except Exception as e:
            logger.error(f"GenericScraper error for {url}: {e}")
            return None

    async def scrape(self, filters: dict) -> List[ScrapedJob]:
        # Generic scraper doesn't do bulk scraping — used for individual URLs
        return []

    def _guess_source(self, url: str) -> str:
        url_lower = url.lower()
        portals = {
            "linkedin": "linkedin",
            "indeed": "indeed",
            "glassdoor": "glassdoor",
            "ziprecruiter": "ziprecruiter",
            "dice": "dice",
            "monster": "monster",
            "lever.co": "lever",
            "greenhouse.io": "greenhouse",
            "workday": "workday",
            "icims": "icims",
            "taleo": "taleo",
            "smartrecruiters": "smartrecruiters",
            "jobvite": "jobvite",
            "breezy": "breezy",
            "ashby": "ashby",
            "rippling": "rippling",
        }
        for key, name in portals.items():
            if key in url_lower:
                return name
        return "other"

    async def _extract_title(self, page) -> str | None:
        selectors = [
            "h1.job-title", "h1[class*='title']", "h1[class*='job']",
            ".job-title h1", ".posting-headline h2", "h1",
            "[class*='JobTitle']", "[data-testid*='title']",
        ]
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if text and len(text) < 200:
                        return text
            except Exception:
                continue
        # Fallback: page title
        title = await page.title()
        return title.split("|")[0].strip() if title else None

    async def _extract_company(self, page, url: str) -> str | None:
        selectors = [
            ".company-name", "[class*='company']", "[class*='employer']",
            "[data-testid*='company']", ".organization-name",
        ]
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if text and len(text) < 100:
                        return text
            except Exception:
                continue
        return None

    async def _extract_location(self, page) -> str | None:
        selectors = [
            ".location", "[class*='location']", "[class*='Location']",
            "[data-testid*='location']", ".job-location",
        ]
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if text and len(text) < 150:
                        return text
            except Exception:
                continue
        return None

    async def _extract_description(self, page) -> str:
        selectors = [
            ".job-description", "#job-description", "[class*='description']",
            ".posting-description", ".job-details", "article",
        ]
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if len(text) > 200:
                        return text[:5000]
            except Exception:
                continue
        return ""
