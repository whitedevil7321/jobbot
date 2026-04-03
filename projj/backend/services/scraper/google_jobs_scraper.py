"""
Google Jobs / additional job scrapers.
Google Jobs widget URL changed — now handled via direct search.
Also includes HiringCafe (free, no auth, great for tech jobs).
"""
import asyncio
import logging
import re
import json as _json
from typing import List
from urllib.parse import urlencode, unquote

import httpx
from bs4 import BeautifulSoup

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
    Scrapes multiple reliable free job sources:
    1. HiringCafe — great for remote/tech jobs, free API
    2. Remotive extra pages
    3. WorkableJob board public listings
    Falls back gracefully if any source fails.
    """
    jobs: List[ScrapedJob] = []
    keywords = _keywords(filters) or "software engineer"

    # Run all sub-scrapers concurrently
    results = await asyncio.gather(
        _scrape_hiringcafe(keywords, filters),
        _scrape_jobicy(keywords, filters),
        _scrape_wellfound(keywords, filters),
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


async def _scrape_hiringcafe(keywords: str, filters: dict) -> List[ScrapedJob]:
    """HiringCafe — free public API, great for tech/remote jobs."""
    jobs = []
    try:
        params = {
            "query": keywords,
            "remote": "true",
            "page": "1",
        }
        url = "https://hiring.cafe/api/search/jobs?" + urlencode(params)
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return jobs
            data = r.json()
            for item in data.get("jobs", data if isinstance(data, list) else []):
                title = item.get("title") or item.get("job_title", "")
                if not title:
                    continue
                link = item.get("url") or item.get("job_url") or item.get("apply_url", "")
                company = item.get("company") or item.get("company_name", "")
                location = item.get("location", "Remote")
                jobs.append(ScrapedJob(
                    source="google",
                    url=link or f"https://hiring.cafe/jobs/{title.replace(' ', '-').lower()}",
                    title=title,
                    company=company,
                    location=location,
                    remote=True,
                    description=item.get("description", "")[:3000],
                    apply_url=link,
                ))
    except Exception as e:
        logger.debug(f"HiringCafe error: {e}")
    return jobs


async def _scrape_jobicy(keywords: str, filters: dict) -> List[ScrapedJob]:
    """Jobicy — free remote jobs API, no auth needed."""
    jobs = []
    try:
        # Jobicy has a free RSS/JSON feed
        url = f"https://jobicy.com/api/v2/remote-jobs?count=20&geo=USA&industry=tech&tag={urlencode({'': keywords})[1:]}"
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            r = await client.get("https://jobicy.com/api/v2/remote-jobs?count=20&geo=USA&industry=tech")
            if r.status_code != 200:
                return jobs
            data = r.json()
            for item in data.get("jobs", []):
                title = item.get("jobTitle", "")
                if not title:
                    continue
                # Filter by keywords
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
                    skills_required=item.get("jobIndustry", []) if isinstance(item.get("jobIndustry"), list) else [],
                    apply_url=link,
                    external_id=str(item.get("id", "")),
                ))
    except Exception as e:
        logger.debug(f"Jobicy error: {e}")
    return jobs


async def _scrape_wellfound(keywords: str, filters: dict) -> List[ScrapedJob]:
    """
    Scrapes Wellfound (AngelList) public job listings via their search API.
    Good for startup jobs and tech roles.
    """
    jobs = []
    try:
        # Use their public search endpoint
        params = {"q": keywords, "remote": "true"}
        url = "https://wellfound.com/jobs?" + urlencode(params)
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return jobs
            soup = BeautifulSoup(r.text, "html.parser")

            # Extract JSON-LD job listings
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = _json.loads(script.string or "")
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        items = [data]
                    else:
                        continue
                    for item in items:
                        if item.get("@type") not in ("JobPosting", "jobPosting"):
                            continue
                        title = item.get("title", "")
                        if not title:
                            continue
                        company = item.get("hiringOrganization", {})
                        if isinstance(company, dict):
                            company = company.get("name", "")
                        apply_url = item.get("url") or item.get("jobUrl", "")
                        jobs.append(ScrapedJob(
                            source="google",
                            url=apply_url or url,
                            title=title,
                            company=company,
                            location="Remote",
                            remote=True,
                            description=item.get("description", "")[:3000],
                            apply_url=apply_url,
                        ))
                except Exception:
                    continue
    except Exception as e:
        logger.debug(f"Wellfound error: {e}")
    return jobs


def _keywords(filters: dict) -> str:
    kw = filters.get("keywords") or filters.get("domains") or []
    if isinstance(kw, list):
        return " ".join(kw) if kw else ""
    return str(kw)
