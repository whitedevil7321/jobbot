"""Detect and classify form fields on job application pages."""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Map field labels to profile attribute names
FIELD_MAP = {
    # Name fields
    r"first\s*name": "first_name",
    r"last\s*name": "last_name",
    r"full\s*name": "full_name",
    # Contact
    r"email": "email",
    r"phone|telephone|mobile": "phone",
    r"address|street": "address",
    r"city": "city",
    r"state|province": "state",
    r"zip|postal": "zip_code",
    r"country": "country",
    # Professional
    r"linkedin": "linkedin_url",
    r"github": "github_url",
    r"portfolio|website|personal\s*url": "portfolio_url",
    r"years\s*of\s*experience|experience\s*years|how\s*many\s*years": "years_of_exp",
    # Education
    r"school|university|college|institution": "school_name",
    r"degree|education\s*level": "degree",
    r"graduation|grad\s*year": "graduation_year",
    r"major|field\s*of\s*study": "degree",
    # Work authorization
    r"work\s*authori|legally\s*authori|eligible\s*to\s*work": "work_auth_eligible",
    r"visa\s*sponsor|require\s*sponsor|need\s*sponsor": "visa_sponsorship_needed",
    # Salary
    r"salary\s*expect|desired\s*salary|compensation\s*expect": "desired_salary_min",
    r"minimum\s*salary": "desired_salary_min",
    # EEO/Demographics
    r"gender|sex": "gender",
    r"ethnicity|race": "ethnicity",
    r"veteran": "veteran_status",
    r"disability": "disability_status",
    # Cover letter
    r"cover\s*letter": "cover_letter",
    r"resume|cv": "resume",
    # Summary/bio
    r"summary|about\s*yourself|tell\s*us\s*about": "summary",
    r"skills": "skills",
}


def map_label_to_field(label: str) -> Optional[str]:
    label_lower = label.lower().strip()
    for pattern, field_name in FIELD_MAP.items():
        if re.search(pattern, label_lower):
            return field_name
    return None


def get_profile_value(profile, field_name: str, question: str = "") -> str:
    """Get the value from the profile for a given field name."""
    import json
    mapping = {
        "full_name": profile.full_name or "",
        "first_name": (profile.full_name or "").split()[0] if profile.full_name else "",
        "last_name": " ".join((profile.full_name or "").split()[1:]) if profile.full_name else "",
        "email": profile.email or "",
        "phone": profile.phone or "",
        "address": profile.address or "",
        "city": profile.city or "",
        "state": profile.state or "",
        "zip_code": profile.zip_code or "",
        "country": profile.country or "United States",
        "linkedin_url": profile.linkedin_url or "",
        "github_url": profile.github_url or "",
        "portfolio_url": profile.portfolio_url or "",
        "years_of_exp": str(profile.years_of_exp or 0),
        "school_name": profile.school_name or "",
        "degree": profile.degree or "",
        "graduation_year": str(profile.graduation_year or ""),
        "gender": profile.gender or "Prefer not to say",
        "ethnicity": profile.ethnicity or "Prefer not to say",
        "veteran_status": profile.veteran_status or "I am not a veteran",
        "disability_status": profile.disability_status or "I don't wish to answer",
        "desired_salary_min": str(profile.desired_salary_min or ""),
        "summary": profile.summary or "",
        "skills": ", ".join(json.loads(profile.skills)) if profile.skills else "",
        "work_auth_eligible": "Yes",
        "visa_sponsorship_needed": "No" if not profile.visa_sponsorship_needed else "Yes",
    }
    return mapping.get(field_name, "")
