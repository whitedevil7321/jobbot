COVER_LETTER_PROMPT = """You are a professional cover letter writer. Write a concise, compelling 3-paragraph cover letter for this job application.

Job Title: {job_title}
Company: {company}
Job Description:
{job_description}

Applicant Profile:
Name: {full_name}
Summary: {summary}
Skills: {skills}
Years of Experience: {years_of_exp}
Target Roles: {target_roles}

Instructions:
- Paragraph 1: Express enthusiasm for the specific role and company
- Paragraph 2: Highlight 2-3 most relevant skills/experiences from the profile
- Paragraph 3: Strong closing with call to action
- Keep it under 300 words
- Do NOT mention anything not in the profile
- Start directly with "Dear Hiring Manager,"

Cover Letter:"""

QUESTION_ANSWER_PROMPT = """You are helping fill out a job application form. Answer the following question based ONLY on the provided profile information. Be concise and truthful.

Question: {question}

Applicant Profile:
Name: {full_name}
Email: {email}
Phone: {phone}
Location: {location}
Years of Experience: {years_of_exp}
Work Authorization: {work_auth}
Visa Sponsorship Needed: {visa_sponsorship_needed}
Skills: {skills}
Education: {degree} from {school_name} ({graduation_year})
Desired Salary: {desired_salary_min} - {desired_salary_max} {salary_currency}

Answer (be direct, 1-3 sentences max):"""

RESUME_TAILOR_PROMPT = """You are a professional resume writer. Rewrite the following resume bullet points to better match the job description. Keep the same facts but use relevant keywords from the job description.

Job Description Keywords: {keywords}

Original Resume Bullets:
{resume_bullets}

Rewritten Bullets (keep same format, same number of bullets):"""

VISA_DETECT_PROMPT = """Does this job description indicate that the employer offers visa sponsorship?
Reply with only one word: yes, no, or unknown.

Job Description:
{description}

Answer:"""

SALARY_DETECT_PROMPT = """Extract the salary range from this job description. Return in format "min,max,currency" or "unknown" if not found.

Job Description:
{description}

Answer:"""

YES_NO_PROMPT = """Answer this yes/no question for the job application. Reply with only "Yes" or "No".

Question: {question}

Profile facts:
- Work Authorization: {work_auth}
- Visa Sponsorship Needed: {visa_sponsorship_needed}
- Years of Experience: {years_of_exp}
- Skills: {skills}
- Location: {location}

Answer:"""
