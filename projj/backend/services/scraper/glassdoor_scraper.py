import asyncio
import logging
from typing import List
from urllib.parse import urlencode
from backend.services.scraper.base_scraper import BaseScraper, ScrapedJob

logger = logging.getLogger(__name__)


class GlassdoorScraper(BaseScraper):
    name = "glassdoor"

    async def scrape(self, filters: dict) -> List[ScrapedJob]:
        jobs = []
        try:
            page = await self.context.new_page()
            keywords = filters.get("keywords", "software engineer")
            if isinstance(keywords, list):
                keywords = " ".join(keywords) if keywords else "software engineer"
            locations = filters.get("locations", ["United States"])

            for location in locations[:2]:
                url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={keywords.replace(' ', '+')}&locT=N&locId=1&jobType=fulltime&fromAge=1&minSalary=0&includeNoSalaryJobs=true&radius=100&cityId=-1&minRating=0.0&industryId=-1&sgocId=-1&seniorityType=all&applicationType=0&remoteWorkType=0"
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await self.human_delay(3, 5)

                    for _ in range(2):
                        await page.evaluate("window.scrollBy(0, 700)")
                        await asyncio.sleep(0.8)

                    job_cards = await page.query_selector_all("li.react-job-listing, article.JobCard_jobCard__RVGEr")
                    logger.info(f"Glassdoor: found {len(job_cards)} cards")

                    for card in job_cards[:15]:
                        try:
                            job = await self._parse_card(card)
                            if job:
                                jobs.append(job)
                        except Exception as e:
                            logger.debug(f"Glassdoor card error: {e}")

                    await self.human_delay(3, 6)
                except Exception as e:
                    logger.error(f"Glassdoor scrape error: {e}")

            await page.close()
        except Exception as e:
            logger.error(f"Glassdoor scraper fatal: {e}")
        return jobs

    async def _parse_card(self, card) -> ScrapedJob | None:
        try:
            title_el = await card.query_selector("[data-test='job-title'], .JobCard_jobTitle__GLyJ1")
            company_el = await card.query_selector("[data-test='employer-name'], .EmployerProfile_compactEmployerName__LE242")
            location_el = await card.query_selector("[data-test='emp-location'], .JobCard_location__N_iYE")
            salary_el = await card.query_selector("[data-test='detailSalary'], .JobCard_salaryEstimate__arV5J")
            link_el = await card.query_selector("a[data-test='job-link'], a.JobCard_trackingLink__zUSOo")

            title = (await title_el.inner_text()).strip() if title_el else None
            company = (await company_el.inner_text()).strip() if company_el else None
            location = (await location_el.inner_text()).strip() if location_el else None
            salary_text = (await salary_el.inner_text()).strip() if salary_el else None
            href = await link_el.get_attribute("href") if link_el else None

            if not title or not href:
                return None

            url = href if href.startswith("http") else "https://www.glassdoor.com" + href
            salary_min, salary_max = self.parse_salary(salary_text or "")
            remote = "remote" in (location or "").lower()

            return ScrapedJob(
                source="glassdoor",
                url=url,
                title=title,
                company=company,
                location=location,
                remote=remote,
                salary_min=salary_min,
                salary_max=salary_max,
                apply_url=url,
            )
        except Exception as e:
            logger.debug(f"Glassdoor _parse_card error: {e}")
            return None
