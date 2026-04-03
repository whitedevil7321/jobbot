"""
Google Jobs / additional job scrapers.
Uses reliable free public job feeds — no authentication required.
Sources: Jobicy API, We Work Remotely RSS, Remote.co RSS.
Falls back gracefully if any source fails.
"""
import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from typing import List
from urllib.parse import urlencode

import httpx

from backend.services.scraper.base_scraper import ScrapedJob

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "application/json, text/html, */*",
}


async def scrape_google_jobs(filters: dict) -> List[ScrapedJob]:
    """
    Scrapes multiple reliable free job sources concurrently:
    1. Jobicy — free remote jobs JSON API
    2. We Work Remotely — free RSS feed (great for remote tech jobs)
    3. Remote.co — free RSS feed
    Falls back gracefully if any source fails.
    """
    jobs: List[ScrapedJob] = []
    keywords = _keywords(filters) or "software engineer"

    results = await asyncio.gather(
        _scrape_jobicy(keywords, filters),
        _scrape_workingnomads(keywords, filters),
        _scrape_remoteco(keywords, filters),
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, list):
            jobs.extend(r)
        elif isinstance(r, Exception):
            logger.debug(f"Sub-scraper error: {r}")

    # Deduplicate by title+company
    seen = set()
    unique = []
    for j in jobs:
        key = f"{j.title}|{j.company}"
        if key not in seen:
            seen.add(key)
            unique.append(j)

    logger.info(f"Google/Tech scrapers: {len(unique)} jobs for '{keywords}'")
    return unique


async def _scrape_jobicy(keywords: str, filters: dict) -> List[ScrapedJob]:
    """Jobicy — free remote jobs JSON API, no auth needed."""
    jobs = []
    try:
        # Use short first keyword for tag filter; fall back to broad tech search
        tag = keywords.split()[0] if keywords else ""
        base = "https://jobicy.com/api/v2/remote-jobs?count=20&geo=usa&industry=engineering"
        url = base + (f"&tag={tag}" if tag else "")

        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                logger.debug(f"Jobicy returned {r.status_code}")
                return jobs
            data = r.json()
            for item in data.get("jobs", []):
                title = item.get("jobTitle", "")
                if not title:
                    continue
                # Keyword filter
                if keywords and not any(
                    kw.lower() in title.lower() or kw.lower() in item.get("jobExcerpt", "").lower()
                    for kw in keywords.split()
                ):
                    continue
                link = item.get("url", "")
                jobs.append(ScrapedJob(
                    source="google",
                    url=link,
                    title=title,
                    company=item.get("companyName", ""),
                    location=item.get("jobGeo", "Remote"),
                    remote=True,
                    description=item.get("jobExcerpt", "")[:3000],
                    skills_required=(
                        item.get("jobIndustry", [])
                        if isinstance(item.get("jobIndustry"), list)
                        else []
                    ),
                    apply_url=link,
                    external_id=str(item.get("id", "")),
                ))
    except Exception as e:
        logger.debug(f"Jobicy error: {e}")
    return jobs


async def _scrape_workingnomads(keywords: str, filters: dict) -> List[ScrapedJob]:
    """
    Working Nomads — free public JSON API, no bot protection, tech-focused remote jobs.
    API docs: https://www.workingnomads.com/api/exposed_jobs/
    """
    jobs = []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            r = await client.get(
                "https://www.workingnomads.com/api/exposed_jobs/?limit=50",
                headers={**HEADERS, "Accept": "application/json"},
            )
            if r.status_code != 200:
                logger.debug(f"WorkingNomads returned {r.status_code}")
                return jobs
            data = r.json()

        items = data if isinstance(data, list) else data.get("results", data.get("jobs", []))
        for item in items:
            title = (item.get("title") or item.get("job_title") or "").strip()
            if not title:
                continue
            # Keyword filter — use first two words for looser match
            kws = keywords.split()[:3] if keywords else []
            if kws and not any(kw.lower() in title.lower() for kw in kws):
                continue

            link = item.get("url") or item.get("apply_url") or ""
            company = item.get("company") or item.get("company_name") or ""
            desc = item.get("description") or item.get("excerpt") or ""
            clean_desc = re.sub(r"<[^>]+>", " ", desc).strip()

            jobs.append(ScrapedJob(
                source="google",
                url=link,
                title=title,
                company=company,
                location="Remote",
                remote=True,
                description=clean_desc[:3000],
                apply_url=link,
                external_id=str(item.get("id") or item.get("slug") or ""),
            ))

    except Exception as e:
        logger.debug(f"WorkingNomads error: {e}")
    return jobs


async def _scrape_remoteco(keywords: str, filters: dict) -> List[ScrapedJob]:
    """Remote.co — free public RSS feed for remote jobs."""
    jobs = []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            r = await client.get("https://remote.co/remote-jobs/feed/")
            if r.status_code != 200:
                logger.debug(f"Remote.co returned {r.status_code}")
                return jobs

        root = ET.fromstring(r.text)
        channel = root.find("channel")
        if channel is None:
            return jobs

        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()

            if not title or not link:
                continue

            # Extract company from title "Job Title at Company"
            company = None
            if " at " in title:
                parts = title.rsplit(" at ", 1)
                title = parts[0].strip()
                company = parts[1].strip()

            clean_desc = re.sub(r"<[^>]+>", " ", desc).strip()
            clean_desc = re.sub(r"\s+", " ", clean_desc)

            # Keyword filter
            if keywords and not any(kw.lower() in title.lower() for kw in keywords.split()):
                continue

            jobs.append(ScrapedJob(
                source="google",
                url=link,
                title=title,
                company=company,
                location="Remote",
                remote=True,
                description=clean_desc[:3000],
                apply_url=link,
            ))

    except Exception as e:
        logger.debug(f"Remote.co error: {e}")
    return jobs


def _keywords(filters: dict) -> str:
    kw = filters.get("keywords") or filters.get("domains") or []
    if isinstance(kw, list):
        return " ".join(kw) if kw else ""
    return str(kw)
