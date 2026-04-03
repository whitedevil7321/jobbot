"""
Google Jobs scraper — scrapes Google's job search results page.
No account needed. Uses httpx + BeautifulSoup.
"""
import asyncio
import logging
import re
import json as _json
from typing import List
from urllib.parse import urlencode

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def scrape_google_jobs(filters: dict) -> List[ScrapedJob]:
    """Scrape Google Jobs search results."""
    jobs: List[ScrapedJob] = []
    keywords = _keywords(filters) or "software engineer"
    locations = filters.get("locations", ["remote"])
    if not locations:
        locations = ["remote"]

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=25, follow_redirects=True) as client:
            for location in locations[:2]:
                query = f"{keywords} jobs"
                if location.lower() != "remote":
                    query += f" in {location}"
                else:
                    query += " remote"

                params = {
                    "q": query,
                    "ibp": "htl;jobs",   # Google Jobs widget
                    "hl": "en",
                }
                url = "https://www.google.com/search?" + urlencode(params)
                try:
                    r = await client.get(url)
                    if r.status_code == 200:
                        extracted = _parse_google_jobs_html(r.text, location)
                        jobs.extend(extracted)
                        logger.info(f"Google Jobs: {len(extracted)} jobs for '{keywords}' in '{location}'")
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Google Jobs error for {location}: {e}")

    except Exception as e:
        logger.error(f"Google Jobs scraper fatal error: {e}")

    return jobs


async def scrape_google_jobs_serpapi_free(filters: dict) -> List[ScrapedJob]:
    """
    Scrape jobs using the free SerpApi Google Jobs endpoint alternative.
    Uses jobs.google.com directly via structured data.
    """
    jobs: List[ScrapedJob] = []
    keywords = _keywords(filters) or "software engineer"
    locations = filters.get("locations", ["remote"])
    if not locations:
        locations = ["remote"]

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=25, follow_redirects=True) as client:
            for location in locations[:2]:
                params = {
                    "q": f"{keywords}",
                    "l": location,
                    "chips": "date_posted:today",
                    "hl": "en",
                    "gl": "us",
                }
                url = "https://www.google.com/search?" + urlencode(params) + "&ibp=htl;jobs"
                try:
                    r = await client.get(url)
                    extracted = _parse_google_jobs_html(r.text, location)
                    jobs.extend(extracted)
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Google Jobs (alt) error: {e}")

    except Exception as e:
        logger.error(f"Google Jobs scraper error: {e}")

    return jobs


def _parse_google_jobs_html(html: str, location: str) -> List[ScrapedJob]:
    """Parse Google Jobs results from HTML — extracts from JSON-LD and HTML cards."""
    jobs = []
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Method 1: JSON-LD structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = _json.loads(script.string or "")
                if isinstance(data, list):
                    for item in data:
                        j = _ld_to_job(item)
                        if j:
                            jobs.append(j)
                elif isinstance(data, dict):
                    j = _ld_to_job(data)
                    if j:
                        jobs.append(j)
            except Exception:
                continue

        # Method 2: Google Jobs widget HTML cards
        cards = soup.select("div[jscontroller][data-hveid], div.PwjeAc, li[jscontroller]")
        for card in cards:
            try:
                title_el = card.select_one("div.BjJfJf, h2, [role='heading']")
                company_el = card.select_one("div.vNEEBe, .oNwCmf, .nJlQNd")
                location_el = card.select_one("div.Qk80Jf, .location, [class*='location']")
                salary_el = card.select_one("div.SuWscb, [class*='salary']")
                link_el = card.select_one("a[href]")

                title = title_el.get_text(strip=True) if title_el else None
                company = company_el.get_text(strip=True) if company_el else None
                job_location = location_el.get_text(strip=True) if location_el else location
                salary_text = salary_el.get_text(strip=True) if salary_el else ""
                href = link_el.get("href", "") if link_el else ""

                if not title:
                    continue

                # Clean Google redirect URLs
                if href.startswith("/url?"):
                    match = re.search(r"[?&]url=([^&]+)", href)
                    if match:
                        from urllib.parse import unquote
                        href = unquote(match.group(1))

                if not href or href.startswith("/"):
                    href = f"https://www.google.com/search?q={title.replace(' ', '+')}+job"

                # Parse salary
                salary_min, salary_max = None, None
                if salary_text:
                    nums = re.findall(r"\$?([\d,]+)k?", salary_text.lower().replace(",", ""))
                    if len(nums) >= 2:
                        salary_min = int(float(nums[0]) * (1000 if "k" in salary_text.lower() else 1))
                        salary_max = int(float(nums[1]) * (1000 if "k" in salary_text.lower() else 1))

                remote = "remote" in (job_location or "").lower()

                if title and href:
                    jobs.append(ScrapedJob(
                        source="google",
                        url=href,
                        title=title,
                        company=company,
                        location=job_location,
                        remote=remote,
                        salary_min=salary_min,
                        salary_max=salary_max,
                        apply_url=href,
                    ))
            except Exception:
                continue

    except Exception as e:
        logger.error(f"Google Jobs HTML parse error: {e}")

    # Deduplicate by title+company
    seen = set()
    unique = []
    for j in jobs:
        key = f"{j.title}|{j.company}"
        if key not in seen:
            seen.add(key)
            unique.append(j)

    return unique


def _ld_to_job(data: dict) -> ScrapedJob | None:
    """Convert JSON-LD JobPosting schema to ScrapedJob."""
    try:
        if data.get("@type") not in ("JobPosting", "jobPosting"):
            return None
        title = data.get("title", "")
        if not title:
            return None
        company = data.get("hiringOrganization", {})
        if isinstance(company, dict):
            company = company.get("name", "")
        location_data = data.get("jobLocation", {})
        if isinstance(location_data, list):
            location_data = location_data[0] if location_data else {}
        address = location_data.get("address", {}) if isinstance(location_data, dict) else {}
        if isinstance(address, str):
            location = address
        elif isinstance(address, dict):
            location = ", ".join(filter(None, [
                address.get("addressLocality"),
                address.get("addressRegion"),
                address.get("addressCountry"),
            ]))
        else:
            location = ""

        remote_type = data.get("jobLocationType", "")
        remote = "telecommute" in remote_type.lower() or "remote" in location.lower()

        salary_data = data.get("baseSalary", {})
        salary_min = salary_max = None
        if isinstance(salary_data, dict):
            val = salary_data.get("value", {})
            if isinstance(val, dict):
                salary_min = val.get("minValue")
                salary_max = val.get("maxValue")

        apply_url = data.get("url") or data.get("jobUrl") or ""

        return ScrapedJob(
            source="google",
            url=apply_url or f"https://www.google.com/search?q={title.replace(' ', '+')}",
            title=title,
            company=company,
            location=location or "Unknown",
            remote=remote,
            salary_min=int(salary_min) if salary_min else None,
            salary_max=int(salary_max) if salary_max else None,
            description=data.get("description", "")[:3000],
            apply_url=apply_url,
        )
    except Exception:
        return None


def _keywords(filters: dict) -> str:
    kw = filters.get("keywords") or filters.get("domains") or []
    if isinstance(kw, list):
        return " ".join(kw) if kw else ""
    return str(kw)
