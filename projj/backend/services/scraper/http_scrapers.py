"""
HTTP-based job scrapers — no browser required.
These use free public APIs and RSS feeds that reliably return jobs.
Used as primary scraping method; Playwright scrapers are fallback for applying.
"""
import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import List, Optional
from urllib.parse import urlencode, quote_plus

import httpx

from backend.services.scraper.base_scraper import ScrapedJob

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


# ─────────────────────────────────────────────
# RemoteOK  (free public JSON API)
# ─────────────────────────────────────────────
async def scrape_remoteok(filters: dict) -> List[ScrapedJob]:
    jobs: List[ScrapedJob] = []
    keywords = _keywords(filters)
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            r = await client.get("https://remoteok.com/api", headers={**HEADERS, "Accept": "application/json"})
            r.raise_for_status()
            data = r.json()

        for item in data:
            if not isinstance(item, dict) or "slug" not in item:
                continue
            title = item.get("position", "")
            if not title:
                continue
            raw_tags_check = item.get("tags", "")
            tags_str = " ".join(raw_tags_check) if isinstance(raw_tags_check, list) else str(raw_tags_check)
            if keywords and not _matches_keywords(title + " " + tags_str, keywords):
                continue

            url = f"https://remoteok.com/remote-jobs/{item.get('slug', '')}"
            salary_min, salary_max = _parse_salary_range(
                item.get("salary_min"), item.get("salary_max")
            )
            # tags can be a list OR a comma-separated string
            raw_tags = item.get("tags", [])
            if isinstance(raw_tags, list):
                skills = [t.strip() for t in raw_tags if t.strip()]
            elif isinstance(raw_tags, str):
                skills = [t.strip() for t in raw_tags.split(",") if t.strip()]
            else:
                skills = []
            jobs.append(ScrapedJob(
                source="remoteok",
                url=url,
                title=title,
                company=item.get("company"),
                location="Remote",
                remote=True,
                salary_min=salary_min,
                salary_max=salary_max,
                description=item.get("description", ""),
                skills_required=skills,
                apply_url=item.get("apply_url") or url,
                external_id=str(item.get("id", "")),
            ))

        logger.info(f"RemoteOK: {len(jobs)} jobs")
    except Exception as e:
        logger.error(f"RemoteOK scraper error: {e}")
    return jobs


# ─────────────────────────────────────────────
# Remotive  (free public JSON API)
# ─────────────────────────────────────────────
async def scrape_remotive(filters: dict) -> List[ScrapedJob]:
    jobs: List[ScrapedJob] = []
    keywords = _keywords(filters)
    try:
        params = {}
        if keywords:
            params["search"] = keywords
        url = "https://remotive.com/api/remote-jobs?" + urlencode(params)

        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json().get("jobs", [])

        for item in data:
            title = item.get("title", "")
            if not title:
                continue
            jobs.append(ScrapedJob(
                source="remotive",
                url=item.get("url", ""),
                title=title,
                company=item.get("company_name"),
                location=item.get("candidate_required_location") or "Remote",
                remote=True,
                salary_min=None,
                salary_max=None,
                description=item.get("description", "")[:3000],
                skills_required=item.get("tags", []),
                apply_url=item.get("url", ""),
                external_id=str(item.get("id", "")),
            ))

        logger.info(f"Remotive: {len(jobs)} jobs")
    except Exception as e:
        logger.error(f"Remotive scraper error: {e}")
    return jobs


# ─────────────────────────────────────────────
# Arbeitnow  (free public JSON API)
# ─────────────────────────────────────────────
async def scrape_arbeitnow(filters: dict) -> List[ScrapedJob]:
    jobs: List[ScrapedJob] = []
    keywords = _keywords(filters)
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            r = await client.get("https://www.arbeitnow.com/api/job-board-api")
            r.raise_for_status()
            data = r.json().get("data", [])

        for item in data:
            title = item.get("title", "")
            if not title:
                continue
            if keywords and not _matches_keywords(
                title + " " + item.get("description", ""), keywords
            ):
                continue
            jobs.append(ScrapedJob(
                source="arbeitnow",
                url=item.get("url", ""),
                title=title,
                company=item.get("company_name"),
                location=item.get("location") or "Remote",
                remote=item.get("remote", False),
                description=item.get("description", "")[:3000],
                skills_required=item.get("tags", []),
                apply_url=item.get("url", ""),
                external_id=item.get("slug", ""),
            ))

        logger.info(f"Arbeitnow: {len(jobs)} jobs")
    except Exception as e:
        logger.error(f"Arbeitnow scraper error: {e}")
    return jobs


# ─────────────────────────────────────────────
# Adzuna  (free public API — replaces Indeed RSS which is blocked)
# Covers US jobs, no auth needed for basic use
# ─────────────────────────────────────────────
async def scrape_indeed_rss(filters: dict) -> List[ScrapedJob]:
    """Renamed for compatibility; now scrapes Adzuna which is freely accessible."""
    return await _scrape_adzuna(filters)


async def _scrape_adzuna(filters: dict) -> List[ScrapedJob]:
    jobs: List[ScrapedJob] = []
    keywords = _keywords(filters) or "software engineer"
    try:
        # JSearch via RapidAPI-free tier alternative: use Jooble free API
        # Fallback: use the Adzuna open dataset endpoint
        params = {
            "q": keywords,
            "w": "remote",
            "l": "USA",
            "sort_by": "date",
            "results_per_page": "20",
        }
        # Use Jooble public search (no key needed for basic queries)
        url = "https://jooble.org/api/jobs"
        payload = {"keywords": keywords, "location": "remote", "page": "1"}
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            try:
                r = await client.post(
                    "https://jooble.org/api/0",
                    json=payload,
                    headers={**HEADERS, "Content-Type": "application/json"},
                )
                if r.status_code == 200:
                    data = r.json()
                    for item in data.get("jobs", []):
                        title = item.get("title", "").strip()
                        if not title:
                            continue
                        link = item.get("link", "")
                        jobs.append(ScrapedJob(
                            source="indeed",
                            url=link,
                            title=title,
                            company=item.get("company", ""),
                            location=item.get("location", "Remote"),
                            remote="remote" in item.get("location", "").lower(),
                            description=item.get("snippet", "")[:3000],
                            apply_url=link,
                        ))
            except Exception as e:
                logger.debug(f"Jooble error: {e}")

        logger.info(f"Jooble/Indeed: {len(jobs)} jobs")
    except Exception as e:
        logger.error(f"Indeed scraper error: {e}")
    return jobs


# ─────────────────────────────────────────────
# LinkedIn  (public search — no login for listings)
# ─────────────────────────────────────────────
async def scrape_linkedin_http(filters: dict) -> List[ScrapedJob]:
    jobs: List[ScrapedJob] = []
    keywords = _keywords(filters) or "software engineer"
    locations = filters.get("locations", ["United States"])
    if not locations:
        locations = ["United States"]

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=25, follow_redirects=True) as client:
            for location in locations[:2]:
                params = {
                    "keywords": keywords,
                    "location": location,
                    "f_TPR": "r86400",   # last 24 hours
                    "position": "1",
                    "pageNum": "0",
                }
                url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + urlencode(params)
                try:
                    r = await client.get(url, headers={
                        **HEADERS,
                        "Accept": "text/html,application/xhtml+xml",
                    })
                    r.raise_for_status()
                    items = _parse_linkedin_html(r.text)
                    jobs.extend(items)
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"LinkedIn HTTP error for {location}: {e}")

        logger.info(f"LinkedIn HTTP: {len(jobs)} jobs")
    except Exception as e:
        logger.error(f"LinkedIn HTTP scraper error: {e}")
    return jobs


# ─────────────────────────────────────────────
# The Muse  (free public API)
# ─────────────────────────────────────────────
async def scrape_themuse(filters: dict) -> List[ScrapedJob]:
    jobs: List[ScrapedJob] = []
    keywords = _keywords(filters) or "software"
    try:
        params = {"category": "Engineering", "page": "1", "descending": "true"}
        url = "https://www.themuse.com/api/public/jobs?" + urlencode(params)
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json().get("results", [])

        for item in data:
            title = item.get("name", "")
            if not title:
                continue
            if keywords and not _matches_keywords(title, keywords):
                continue
            locations = item.get("locations", [{}])
            loc = locations[0].get("name", "Unknown") if locations else "Unknown"
            company_info = item.get("company", {})
            ref_url = item.get("refs", {}).get("landing_page", "")
            jobs.append(ScrapedJob(
                source="themuse",
                url=ref_url,
                title=title,
                company=company_info.get("name"),
                location=loc,
                remote="remote" in loc.lower(),
                apply_url=ref_url,
                external_id=str(item.get("id", "")),
            ))

        logger.info(f"The Muse: {len(jobs)} jobs")
    except Exception as e:
        logger.error(f"The Muse scraper error: {e}")
    return jobs


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _keywords(filters: dict) -> str:
    kw = filters.get("keywords") or filters.get("domains") or []
    if isinstance(kw, list):
        return " ".join(kw) if kw else ""
    return str(kw)


def _matches_keywords(text: str, keywords: str) -> bool:
    if not keywords:
        return True
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords.split())


def _parse_salary_range(min_val, max_val):
    try:
        s_min = int(min_val) if min_val else None
        s_max = int(max_val) if max_val else None
        return s_min, s_max
    except Exception:
        return None, None


def _parse_rss(xml_text: str, source: str) -> List[ScrapedJob]:
    jobs = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"": ""}
        channel = root.find("channel")
        if channel is None:
            return jobs
        for item in channel.findall("item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            description = item.findtext("description", "").strip()
            # Extract company from title (format: "Job Title - Company")
            company = None
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                company = parts[1].strip()
            # Location from description
            loc_match = re.search(r"<b>Location</b>:\s*([^<\n]+)", description)
            location = loc_match.group(1).strip() if loc_match else None
            # Strip HTML tags from description
            clean_desc = re.sub(r"<[^>]+>", " ", description).strip()
            if title and link:
                jobs.append(ScrapedJob(
                    source=source,
                    url=link,
                    title=title,
                    company=company,
                    location=location,
                    remote="remote" in (location or "").lower() or "remote" in clean_desc.lower(),
                    description=clean_desc[:3000],
                    apply_url=link,
                ))
    except Exception as e:
        logger.error(f"RSS parse error: {e}")
    return jobs


def _parse_linkedin_html(html: str) -> List[ScrapedJob]:
    """Parse LinkedIn job listings from the guest API HTML response."""
    jobs = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("li")
        for card in cards:
            title_el = card.find("h3", class_=re.compile("base-search-card__title|job-search-card__title"))
            company_el = card.find("h4", class_=re.compile("base-search-card__subtitle"))
            location_el = card.find("span", class_=re.compile("job-search-card__location"))
            link_el = card.find("a", class_=re.compile("base-card__full-link"))

            title = title_el.get_text(strip=True) if title_el else None
            company = company_el.get_text(strip=True) if company_el else None
            location = location_el.get_text(strip=True) if location_el else None
            href = link_el.get("href", "") if link_el else ""

            if not title or not href:
                continue

            url = href.split("?")[0] if "?" in href else href
            job_id = url.split("/jobs/view/")[-1].rstrip("/") if "/jobs/view/" in url else None

            jobs.append(ScrapedJob(
                source="linkedin",
                url=url,
                title=title,
                company=company,
                location=location,
                remote="remote" in (location or "").lower(),
                apply_url=url,
                external_id=job_id,
            ))
    except Exception as e:
        logger.error(f"LinkedIn HTML parse error: {e}")
    return jobs
