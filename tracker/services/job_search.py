import re

import httpx
from bs4 import BeautifulSoup

from .utils import clean_job_description

KEYWORDS = [
    'junior business analyst',
    'graduate business analyst',
    'junior data analyst',
    'graduate data analyst',
    'junior developer',
    'junior software developer',
    'junior python developer',
    'graduate developer',
    'graduate software engineer',
    'junior full stack developer',
    'junior backend developer',
    'associate analyst',
    'technical analyst',
    'systems analyst',
]

# Title must contain at least one of these to pass
_TITLE_INCLUDE = re.compile(
    r'\b(junior|graduate|grad|entry.?level|associate|'
    r'business analyst|data analyst|technical analyst|systems analyst|'
    r'full.?stack|python|django)\b',
    re.IGNORECASE,
)

# Block if title contains any of these
_TITLE_BLOCK = re.compile(
    r'\b(senior|sr\b|principal|lead\b|manager|director|head of|'
    r'architect|vice president|\bvp\b)\b',
    re.IGNORECASE,
)

# Block if description explicitly requires 3+ years
# Negative lookbehind for "1-" or "2-" so "1-3 years" and "2-3 years" pass
_EXP_BLOCK = re.compile(
    r'(?<![1-2]-)\b[3-9]\+?\s*years?\s*(of\s+)?(professional\s+)?(experience|exp)\b'
    r'|minimum\s+(of\s+)?[3-9]\s*years?'
    r'|at\s+least\s+[3-9]\s*years?',
    re.IGNORECASE,
)

# Block if explicitly US-only (high bar — don't block on just mentioning US)
_US_ONLY = re.compile(
    r'US\s+citizens?\s+only'
    r'|must\s+be\s+authorized\s+to\s+work\s+in\s+the\s+(US|United States)'
    r'|US\s+work\s+authorization\s+required'
    r'|applicants?\s+must\s+be\s+based\s+in\s+the\s+(US|United States)',
    re.IGNORECASE,
)


class CareerjetSearcher:
    API_KEY = '478b96ecf5c7be8ec57be15b34e84839'
    ENDPOINT = 'https://search.api.careerjet.net/v4/query'

    def search(self, keyword: str) -> list[dict]:
        try:
            response = httpx.get(
                self.ENDPOINT,
                auth=(self.API_KEY, ''),
                params={
                    'locale_code': 'en_IE',
                    'keywords': keyword,
                    'location': 'Dublin',
                    'sort': 'date',
                    'page_size': 50,
                    'user_ip': '8.8.8.8',
                    'user_agent': 'JobTracker/1.0',
                },
                headers={'Referer': 'https://web-production-6cefe.up.railway.app/queue/'},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            if data.get('type') == 'JOBS':
                return data.get('jobs', [])
            return []
        except Exception:
            return []

    def _parse_result(self, job: dict) -> dict:
        raw_description = job.get('description', '')
        description = clean_job_description(
            BeautifulSoup(raw_description, 'html.parser').get_text(separator='\n')
            if '<' in raw_description else raw_description
        )

        return {
            'role': job.get('title', ''),
            'company': job.get('company', ''),
            'location': job.get('locations', ''),
            'salary_range': job.get('salary', ''),
            'job_description': description,
            'source_url': job.get('url', ''),
        }

    def run_all_searches(self) -> list[dict]:
        seen_urls: set[str] = set()
        results: list[dict] = []

        for keyword in KEYWORDS:
            for item in self.search(keyword):
                parsed = self._parse_result(item)
                url = parsed['source_url']
                if not url or url in seen_urls:
                    continue
                if not _should_include(parsed['role'], parsed['job_description']):
                    continue
                seen_urls.add(url)
                results.append(parsed)

        return results


def _should_include(role: str, description: str) -> bool:
    if not _TITLE_INCLUDE.search(role):
        return False
    if _TITLE_BLOCK.search(role):
        return False
    if _EXP_BLOCK.search(description):
        return False
    if _US_ONLY.search(description):
        return False
    return True


def save_leads(job_dicts: list[dict]) -> tuple[int, int]:
    from tracker.models import JobLead  # avoid circular import

    created = 0
    skipped = 0

    for job in job_dicts:
        url = job.get('source_url', '')
        if not url:
            skipped += 1
            continue
        if JobLead.objects.filter(source_url=url).exists():
            skipped += 1
        else:
            JobLead.objects.create(
                company=job.get('company', ''),
                role=job.get('role', ''),
                location=job.get('location', ''),
                salary_range=job.get('salary_range', ''),
                job_description=job.get('job_description', ''),
                source_url=url,
                status=JobLead.STATUS_NEW,
            )
            created += 1

    return created, skipped
