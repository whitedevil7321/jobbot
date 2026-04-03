import json
import logging
from backend.services.llm.ollama_client import ollama
from backend.services.llm.prompts import COVER_LETTER_PROMPT, QUESTION_ANSWER_PROMPT, YES_NO_PROMPT, VISA_DETECT_PROMPT

logger = logging.getLogger(__name__)


def _profile_to_dict(profile) -> dict:
    return {
        "full_name": profile.full_name or "",
        "email": profile.email or "",
        "phone": profile.phone or "",
        "location": profile.location or "",
        "summary": profile.summary or "",
        "skills": ", ".join(json.loads(profile.skills)) if profile.skills else "",
        "years_of_exp": profile.years_of_exp or 0,
        "target_roles": ", ".join(json.loads(profile.target_roles)) if profile.target_roles else "",
        "work_auth": profile.work_auth or "citizen",
        "visa_sponsorship_needed": "Yes" if profile.visa_sponsorship_needed else "No",
        "degree": profile.degree or "N/A",
        "school_name": profile.school_name or "N/A",
        "graduation_year": profile.graduation_year or "N/A",
        "desired_salary_min": profile.desired_salary_min or "Negotiable",
        "desired_salary_max": profile.desired_salary_max or "Negotiable",
        "salary_currency": profile.salary_currency or "USD",
    }


async def generate_cover_letter(profile, job_title: str, company: str, job_description: str) -> str:
    if not await ollama.is_running():
        logger.warning("Ollama not running, skipping cover letter generation")
        return ""
    p = _profile_to_dict(profile)
    prompt = COVER_LETTER_PROMPT.format(
        job_title=job_title,
        company=company or "the company",
        job_description=job_description[:3000] if job_description else "",
        **p,
    )
    result = await ollama.generate(prompt, temperature=0.7)
    return result


async def answer_question(profile, question: str) -> str:
    if not await ollama.is_running():
        return _fallback_answer(profile, question)
    p = _profile_to_dict(profile)
    prompt = QUESTION_ANSWER_PROMPT.format(question=question, **p)
    result = await ollama.generate(prompt, temperature=0.2)
    return result or _fallback_answer(profile, question)


async def answer_yes_no(profile, question: str) -> str:
    if not await ollama.is_running():
        return _fallback_yes_no(profile, question)
    p = _profile_to_dict(profile)
    prompt = YES_NO_PROMPT.format(question=question, **p)
    result = await ollama.generate(prompt, temperature=0.0)
    result = result.strip().lower()
    return "Yes" if "yes" in result else "No"


async def detect_visa_sponsorship(description: str) -> str:
    if not await ollama.is_running() or not description:
        return "unknown"
    prompt = VISA_DETECT_PROMPT.format(description=description[:2000])
    result = await ollama.generate(prompt, temperature=0.0)
    result = result.strip().lower()
    if "yes" in result:
        return "yes"
    elif "no" in result:
        return "no"
    return "unknown"


def _fallback_answer(profile, question: str) -> str:
    q = question.lower()
    if "salary" in q or "compensation" in q:
        if profile.desired_salary_min:
            return f"{profile.desired_salary_min}"
        return "Negotiable"
    if "year" in q and "experience" in q:
        return str(profile.years_of_exp or 0)
    if "authorized" in q or "work" in q and "us" in q:
        return "Yes"
    if "sponsorship" in q or "visa" in q:
        return "No" if not profile.visa_sponsorship_needed else "Yes"
    if "name" in q:
        return profile.full_name or ""
    if "email" in q:
        return profile.email or ""
    if "phone" in q:
        return profile.phone or ""
    if "location" in q or "city" in q:
        return profile.location or ""
    return ""


def _fallback_yes_no(profile, question: str) -> str:
    q = question.lower()
    if "authorized" in q or "eligible" in q:
        return "Yes"
    if "sponsorship" in q or "visa" in q:
        return "No" if not profile.visa_sponsorship_needed else "Yes"
    if "18" in q or "legal" in q:
        return "Yes"
    return "Yes"
