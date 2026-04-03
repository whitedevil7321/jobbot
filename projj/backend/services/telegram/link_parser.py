import re
from typing import Optional

JOB_URL_PATTERNS = [
    r"https?://(?:www\.)?linkedin\.com/jobs/view/[\w-]+",
    r"https?://(?:www\.)?indeed\.com/(?:viewjob|jobs).*",
    r"https?://(?:www\.)?glassdoor\.com/job-listing/.*",
    r"https?://(?:www\.)?ziprecruiter\.com/jobs/.*",
    r"https?://(?:www\.)?dice\.com/jobs/detail/.*",
    r"https?://(?:www\.)?monster\.com/job-openings/.*",
    r"https?://jobs\.lever\.co/.*",
    r"https?://boards\.greenhouse\.io/.*",
    r"https?://.*\.workday\.com/.*jobs.*",
    r"https?://.*\.icims\.com/jobs/.*",
    r"https?://.*\.taleo\.net/.*",
    r"https?://.*smartrecruiters\.com/.*",
    r"https?://.*\.jobvite\.com/.*",
    r"https?://.*\.breezy\.hr/.*",
    r"https?://.*\.ashbyhq\.com/.*",
    r"https?://careers\..*",
    r"https?://jobs\..*",
]

GENERAL_URL_PATTERN = r"https?://[^\s]+"


def extract_job_url(text: str) -> Optional[str]:
    """Extract a job URL from a Telegram message."""
    # Try specific job portal patterns first
    for pattern in JOB_URL_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).rstrip(".,;)")

    # Fall back to any URL
    match = re.search(GENERAL_URL_PATTERN, text)
    if match:
        url = match.group(0).rstrip(".,;)")
        # Basic validation
        if any(kw in url.lower() for kw in ["job", "career", "position", "opening", "apply", "hire"]):
            return url

    return None


def is_job_url(url: str) -> bool:
    for pattern in JOB_URL_PATTERNS:
        if re.match(pattern, url, re.IGNORECASE):
            return True
    return False
