from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List
import random
import asyncio
import logging

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
]


@dataclass
class ScrapedJob:
    source: str
    url: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    remote: bool = False
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: str = "USD"
    description: Optional[str] = None
    required_exp: Optional[int] = None
    skills_required: List[str] = field(default_factory=list)
    domain: Optional[str] = None
    visa_sponsorship: str = "unknown"
    easy_apply: bool = False
    apply_url: Optional[str] = None
    external_id: Optional[str] = None


class BaseScraper(ABC):
    name: str = "base"

    def __init__(self, browser_context=None):
        self.context = browser_context

    async def human_delay(self, min_s: float = 1.5, max_s: float = 4.0):
        await asyncio.sleep(random.uniform(min_s, max_s))

    def random_user_agent(self) -> str:
        return random.choice(USER_AGENTS)

    def random_viewport(self) -> dict:
        return random.choice(VIEWPORTS)

    @abstractmethod
    async def scrape(self, filters: dict) -> List[ScrapedJob]:
        """Scrape jobs matching the given filters. Returns list of ScrapedJob."""
        pass

    def parse_salary(self, text: str) -> tuple[Optional[int], Optional[int]]:
        """Parse salary string like '$80k - $120k' into (80000, 120000)."""
        import re
        if not text:
            return None, None
        text = text.replace(",", "").replace(" ", "")
        pattern = r"\$?([\d.]+)[kK]?\s*[-–]\s*\$?([\d.]+)[kK]?"
        match = re.search(pattern, text)
        if match:
            lo, hi = float(match.group(1)), float(match.group(2))
            if lo < 1000:
                lo *= 1000
            if hi < 1000:
                hi *= 1000
            return int(lo), int(hi)
        single = re.search(r"\$?([\d.]+)[kK]?", text)
        if single:
            v = float(single.group(1))
            if v < 1000:
                v *= 1000
            return int(v), None
        return None, None

    def parse_exp_years(self, text: str) -> Optional[int]:
        """Extract minimum years of experience from text."""
        import re
        if not text:
            return None
        match = re.search(r"(\d+)\+?\s*(?:to\s*\d+\s*)?years?", text.lower())
        if match:
            return int(match.group(1))
        return None
