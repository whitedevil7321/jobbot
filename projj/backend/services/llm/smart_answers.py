"""
Smart answer generator — uses ALL profile data + LLM to answer any job
application question. Falls back gracefully if Ollama is not running.
"""
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Master prompt for unknown questions ───────────────────────────────────
SMART_PROMPT = """You are filling out a job application form on behalf of the applicant.
Answer the question ONLY using the profile information provided. Be concise and professional.
If the answer is not in the profile, give the most reasonable default answer.
Never make up credentials, companies, or skills not listed in the profile.

APPLICANT PROFILE:
{profile_context}

QUESTION: {question}

Answer (be direct, 1–3 sentences max, no preamble):"""


def build_profile_context(profile) -> str:
    """Build a rich text context from all profile fields for the LLM."""
    lines = []
    if profile.full_name:
        lines.append(f"Name: {profile.full_name}")
    if profile.email:
        lines.append(f"Email: {profile.email}")
    if profile.phone:
        lines.append(f"Phone: {profile.phone}")
    if profile.location:
        lines.append(f"Location: {profile.location}")
    if profile.city and profile.state:
        lines.append(f"City/State: {profile.city}, {profile.state}")
    if profile.zip_code:
        lines.append(f"ZIP: {profile.zip_code}")
    if profile.country:
        lines.append(f"Country: {profile.country}")
    lines.append(f"Years of Experience: {profile.years_of_exp or 0}")
    lines.append(f"Work Authorization: {profile.work_auth or 'citizen'}")
    lines.append(f"Needs Visa Sponsorship: {'Yes' if profile.visa_sponsorship_needed else 'No'}")
    if profile.linkedin_url:
        lines.append(f"LinkedIn: {profile.linkedin_url}")
    if profile.github_url:
        lines.append(f"GitHub: {profile.github_url}")
    if profile.portfolio_url:
        lines.append(f"Portfolio: {profile.portfolio_url}")
    if profile.skills:
        try:
            skills = json.loads(profile.skills)
            lines.append(f"Skills: {', '.join(skills)}")
        except Exception:
            lines.append(f"Skills: {profile.skills}")
    if profile.target_roles:
        try:
            roles = json.loads(profile.target_roles)
            lines.append(f"Target Roles: {', '.join(roles)}")
        except Exception:
            pass
    if profile.summary:
        lines.append(f"Summary: {profile.summary}")
    if profile.degree:
        lines.append(f"Degree: {profile.degree}")
    if profile.school_name:
        lines.append(f"School: {profile.school_name}")
    if profile.graduation_year:
        lines.append(f"Graduation Year: {profile.graduation_year}")
    if profile.highest_education:
        lines.append(f"Education Level: {profile.highest_education}")
    if profile.desired_salary_min:
        lines.append(f"Desired Salary Min: ${profile.desired_salary_min:,}")
    if profile.desired_salary_max:
        lines.append(f"Desired Salary Max: ${profile.desired_salary_max:,}")
    lines.append(f"Veteran Status: {profile.veteran_status or 'I am not a veteran'}")
    lines.append(f"Disability Status: {profile.disability_status or 'I do not wish to answer'}")
    if profile.gender:
        lines.append(f"Gender: {profile.gender}")
    if profile.ethnicity:
        lines.append(f"Ethnicity: {profile.ethnicity}")
    return "\n".join(lines)


# ─── Rule-based fast answers (no LLM needed) ──────────────────────────────
RULE_PATTERNS = [
    # Authorization
    (r"(legally|authorized|eligible|right).{0,30}(work|employment|us|usa|united states)", "yes_no_auth"),
    (r"work authorization|work status",                   "work_auth_text"),
    # Sponsorship
    (r"(visa|sponsorship|h[- ]?1b|require.{0,10}sponsor)", "sponsorship"),
    # Personal
    (r"first\s*name",                                     "first_name"),
    (r"last\s*name|surname",                              "last_name"),
    (r"full\s*name|your\s*name",                          "full_name"),
    (r"email|e-mail",                                     "email"),
    (r"phone|telephone|mobile",                           "phone"),
    (r"address|street",                                   "address"),
    (r"\bcity\b",                                         "city"),
    (r"\bstate\b",                                        "state"),
    (r"zip|postal",                                       "zip_code"),
    (r"\bcountry\b",                                      "country"),
    # Professional
    (r"linkedin",                                         "linkedin_url"),
    (r"github",                                           "github_url"),
    (r"portfolio|website|personal\s*url",                 "portfolio_url"),
    (r"years.{0,15}experience|experience.{0,10}years",    "years_exp"),
    (r"salary.{0,20}expect|desired.{0,10}salary|compensation", "salary"),
    (r"minimum.{0,10}salary",                             "salary_min"),
    # Education
    (r"(school|university|college|institution)",          "school"),
    (r"degree|education\s*level",                         "degree"),
    (r"graduation|grad\s*year",                           "grad_year"),
    (r"major|field\s*of\s*study",                         "major"),
    # EEO
    (r"\bgender\b|\bsex\b",                               "gender"),
    (r"ethnicity|race",                                   "ethnicity"),
    (r"veteran",                                          "veteran"),
    (r"disability|disabled",                              "disability"),
    # Misc
    (r"are you 18|over 18|legal age",                     "age_18"),
    (r"willing to relocate|open to reloca",               "relocate"),
    (r"start date|available to start|availability",       "start_date"),
    (r"cover letter",                                     "cover_letter"),
    (r"summary|about yourself",                           "summary"),
]


def fast_answer(profile, question: str) -> Optional[str]:
    """Return an instant rule-based answer without calling the LLM."""
    q = question.lower().strip()

    for pattern, field in RULE_PATTERNS:
        if re.search(pattern, q):
            return _resolve_field(profile, field, q)
    return None


def _resolve_field(profile, field: str, question: str) -> Optional[str]:
    work_auth_map = {
        "citizen":   "I am a US Citizen and do not require sponsorship",
        "greencard": "I have a Green Card and do not require sponsorship",
        "h1b":       "I am on H-1B visa",
        "opt":       "I am on OPT/STEM OPT",
        "tn":        "I am on TN visa",
        "other":     "I have valid work authorization",
    }

    if field == "yes_no_auth":
        return "Yes"
    if field == "work_auth_text":
        return work_auth_map.get(profile.work_auth or "citizen", "Yes, I am authorized to work")
    if field == "sponsorship":
        if profile.visa_sponsorship_needed:
            return "Yes, I require visa sponsorship"
        return "No, I do not require visa sponsorship"
    if field == "first_name":
        name = profile.full_name or ""
        return name.split()[0] if name else ""
    if field == "last_name":
        name = profile.full_name or ""
        parts = name.split()
        return " ".join(parts[1:]) if len(parts) > 1 else ""
    if field == "full_name":
        return profile.full_name or ""
    if field == "email":
        return profile.email or ""
    if field == "phone":
        return profile.phone or ""
    if field == "address":
        return profile.address or profile.location or ""
    if field == "city":
        return profile.city or ""
    if field == "state":
        return profile.state or ""
    if field == "zip_code":
        return profile.zip_code or ""
    if field == "country":
        return profile.country or "United States"
    if field == "linkedin_url":
        return profile.linkedin_url or ""
    if field == "github_url":
        return profile.github_url or ""
    if field == "portfolio_url":
        return profile.portfolio_url or ""
    if field == "years_exp":
        return str(profile.years_of_exp or 0)
    if field == "salary":
        if profile.desired_salary_min and profile.desired_salary_max:
            return f"${profile.desired_salary_min:,} - ${profile.desired_salary_max:,}"
        elif profile.desired_salary_min:
            return f"${profile.desired_salary_min:,}"
        return "Negotiable"
    if field == "salary_min":
        return str(profile.desired_salary_min) if profile.desired_salary_min else "Negotiable"
    if field == "school":
        return profile.school_name or ""
    if field == "degree":
        return profile.degree or profile.highest_education or ""
    if field == "grad_year":
        return str(profile.graduation_year) if profile.graduation_year else ""
    if field == "major":
        return profile.degree or ""
    if field == "gender":
        return profile.gender or "Prefer not to say"
    if field == "ethnicity":
        return profile.ethnicity or "Prefer not to say"
    if field == "veteran":
        return profile.veteran_status or "I am not a veteran"
    if field == "disability":
        return profile.disability_status or "I do not wish to answer"
    if field == "age_18":
        return "Yes"
    if field == "relocate":
        return "Open to discussion"
    if field == "start_date":
        return "2 weeks notice / Immediately"
    if field == "cover_letter":
        return ""  # Cover letter is generated separately
    if field == "summary":
        return profile.summary or ""
    return None


async def smart_answer_question(profile, question: str, job=None) -> str:
    """
    Answer a job application question intelligently.
    1. Try fast rule-based answer first (instant, no LLM).
    2. Fall back to LLM with full profile context.
    3. Final fallback: return empty string.
    """
    # Fast path
    answer = fast_answer(profile, question)
    if answer is not None:
        return answer

    # LLM path
    try:
        from backend.services.llm.ollama_client import ollama
        if not await ollama.is_running():
            return _best_guess_fallback(profile, question)

        context = build_profile_context(profile)
        job_ctx = ""
        if job:
            job_ctx = f"\nJOB: {job.title} at {job.company}\n"

        prompt = SMART_PROMPT.format(
            profile_context=context + job_ctx,
            question=question,
        )
        result = await ollama.generate(prompt, temperature=0.2)
        return result or _best_guess_fallback(profile, question)

    except Exception as e:
        logger.error(f"smart_answer_question error: {e}")
        return _best_guess_fallback(profile, question)


def _best_guess_fallback(profile, question: str) -> str:
    """Last-resort answer with no LLM."""
    q = question.lower()
    if any(w in q for w in ["yes", "no", "are you", "do you", "have you", "can you"]):
        return "Yes"
    if "salary" in q or "compensation" in q:
        return str(profile.desired_salary_min) if profile.desired_salary_min else "Negotiable"
    if "experience" in q:
        return str(profile.years_of_exp or 0)
    if "location" in q or "city" in q:
        return profile.location or profile.city or ""
    return ""
