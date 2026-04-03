import json
import logging
from backend.services.scraper.base_scraper import ScrapedJob

logger = logging.getLogger(__name__)


class FilterEngine:
    def score(self, job: ScrapedJob, filter_config) -> float:
        """Return a score 0-100 for how well a job matches the filter config."""
        if not filter_config:
            return 50.0

        score = 50.0
        description_text = (job.description or "").lower()
        title_text = (job.title or "").lower()

        # --- Location match ---
        if filter_config.locations:
            locations = json.loads(filter_config.locations)
            if locations:
                matched = False
                for loc in locations:
                    if loc.lower() == "remote" and job.remote:
                        matched = True
                        break
                    if loc.lower() in (job.location or "").lower():
                        matched = True
                        break
                    if loc.lower() == "remote" and "remote" in description_text:
                        matched = True
                        break
                if not matched:
                    score -= 30

        # --- Experience match ---
        if job.required_exp is not None:
            min_exp = filter_config.min_years_exp or 0
            max_exp = filter_config.max_years_exp or 20
            if job.required_exp > max_exp:
                score -= 25
            elif job.required_exp >= min_exp:
                score += 10

        # --- Excluded keywords ---
        if filter_config.excluded_keywords:
            excluded = json.loads(filter_config.excluded_keywords)
            for kw in excluded:
                if kw.lower() in title_text:
                    score -= 40
                    break

        # --- Required skills match ---
        if filter_config.required_skills:
            required = json.loads(filter_config.required_skills)
            if required:
                matched_skills = sum(1 for s in required if s.lower() in description_text)
                ratio = matched_skills / len(required)
                score += ratio * 20

        # --- Domain/keyword match ---
        if filter_config.domains:
            domains = json.loads(filter_config.domains)
            if domains:
                matched = any(d.lower() in title_text or d.lower() in description_text for d in domains)
                if matched:
                    score += 15

        # --- Visa sponsorship ---
        if filter_config.visa_sponsorship_filter == "required":
            if job.visa_sponsorship == "no":
                score -= 50
            elif job.visa_sponsorship == "yes":
                score += 15
        elif filter_config.visa_sponsorship_filter == "not_required":
            if job.visa_sponsorship == "yes":
                score -= 10

        # --- Salary match ---
        if filter_config.salary_min and job.salary_min:
            if job.salary_min < filter_config.salary_min:
                score -= 10
        if filter_config.salary_max and job.salary_max:
            if job.salary_max > filter_config.salary_max * 2:
                score -= 5

        # --- Job type ---
        if filter_config.job_types:
            job_types = json.loads(filter_config.job_types)
            if job_types and "full-time" in job_types:
                if "contract" in title_text or "contractor" in title_text:
                    score -= 15

        return max(0.0, min(100.0, score))

    def passes_threshold(self, score: float, threshold: float = 30.0) -> bool:
        return score >= threshold


filter_engine = FilterEngine()
