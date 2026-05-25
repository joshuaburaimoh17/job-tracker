import re
import httpx
import feedparser
from django.conf import settings
from ..models import JobLead

SEARCH_KEYWORDS = [
    # Business / Data Analyst
    'Junior Business Analyst',
    'Graduate Business Analyst',
    'Entry Level Business Analyst',
    'Technical Analyst',
    'Data Analyst',
    'Graduate Data Analyst',
    'Junior Data Analyst',
    'Systems Analyst',
    # Developer / Engineer
    'Junior Developer',
    'Junior Software Developer',
    'Junior Software Engineer',
    'Junior Full Stack Developer',
    'Junior Backend Developer',
    'Junior Python Developer',
    'Junior Django Developer',
    'Graduate Developer',
    'Graduate Software Engineer',
    'Entry Level Developer',
    'Entry Level Software Engineer',
]

# RSS title must contain at least one of these
TITLE_INCLUDE_TERMS = [
    'junior', 'graduate', 'grad ', 'entry level', 'entry-level',
    'business analyst', 'technical analyst', 'data analyst', 'systems analyst',
    'full stack', 'fullstack', 'full-stack',
    'back end', 'backend', 'back-end',
    'python developer', 'django',
]

# Seniority terms that disqualify a role (unless title also has junior/graduate)
_SENIORITY_BLOCK = [
    'senior', ' sr.', ' sr ', 'principal', 'staff engineer',
    ' lead ', 'team lead', 'tech lead', 'lead developer', 'lead engineer',
    'manager', 'head of', 'director', ' vp ', 'vice president', 'architect',
]

# Stack/tool terms that always disqualify
_STACK_BLOCK = [
    'ios developer', 'ios engineer', 'android developer', 'android engineer',
    'mobile developer', 'mobile engineer',
    'salesforce', ' sap ', ',sap,', 'sap developer',
    'embedded', 'firmware',
    'c++ developer', 'c++ engineer',
]

# Stack terms blocked unless the title is explicitly junior/graduate
_STACK_BLOCK_UNLESS_JUNIOR = [
    '.net developer', '.net engineer',
]

# Role types that are out of scope entirely
_ROLE_BLOCK = [
    'sales executive', 'sales representative', 'sales manager', 'sales engineer',
    'account executive', 'account manager',
    'marketing', 'seo ', 'content writer', 'copywriter',
    'graphic designer', 'product designer', 'ux designer', 'ui designer',
    'ux/ui', 'ui/ux', 'motion designer',
    'devops engineer', 'devops developer', 'site reliability', ' sre ',
    'infrastructure engineer', 'cloud engineer', 'network engineer', 'network administrator',
    'security engineer', 'penetration tester', 'pen tester',
]

# Detects "3+ years", "3 years experience", "minimum 3 years", etc.
_EXPERIENCE_RE = re.compile(
    r'\b([3-9]|\d{2,})\s*\+?\s*years?\s*(of\s+)?(experience|exp\b)',
    re.I,
)

# Detects roles that are US-only
_US_ONLY_RE = re.compile(
    r'must be (based|located|residing) in (the )?u\.?s\.?\b'
    r'|u\.?s\.?\s*(work\s+)?authoriz'
    r'|authorized to work in (the )?u\.?s'
    r'|\busa only\b|\bus only\b|united states only'
    r'|must have (us|u\.s\.) (citizenship|work authorization)'
    r'|h[-\s]?1b|us visa sponsor',
    re.I,
)


def _is_junior(title: str) -> bool:
    return bool(re.search(r'\b(junior|graduate|grad|entry.level)\b', title, re.I))


def _should_include(role: str, description: str = '') -> bool:
    title = role.lower()
    desc = description.lower()
    junior = _is_junior(title)

    if not any(term in title for term in TITLE_INCLUDE_TERMS):
        return False

    if not junior and any(term in title for term in _SENIORITY_BLOCK):
        return False

    if any(term in title for term in _STACK_BLOCK):
        return False

    if any(term in title for term in _ROLE_BLOCK):
        return False

    if not junior and any(term in title for term in _STACK_BLOCK_UNLESS_JUNIOR):
        return False

    if description and _EXPERIENCE_RE.search(desc):
        return False

    if description and _US_ONLY_RE.search(desc):
        return False

    return True


class AdzunaSearcher:
    BASE_URL = 'https://api.adzuna.com/v1/api/jobs/{country}/search/1'

    def __init__(self):
        self.app_id = settings.ADZUNA_APP_ID
        self.app_key = settings.ADZUNA_API_KEY

    def search(self, keyword, country='ie', where=None, remote=False):
        params = {
            'app_id': self.app_id,
            'app_key': self.app_key,
            'what': f'{keyword} remote' if remote else keyword,
            'results_per_page': 20,
            'sort_by': 'date',
        }
        if where:
            params['where'] = where
        url = self.BASE_URL.format(country=country)
        try:
            response = httpx.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json().get('results', [])
        except Exception:
            return []

    @staticmethod
    def _format_salary(minimum, maximum):
        if minimum and maximum:
            return f'€{int(minimum):,} – €{int(maximum):,}'
        if minimum:
            return f'From €{int(minimum):,}'
        return ''

    def _parse_result(self, result, source='adzuna'):
        return {
            'company': result.get('company', {}).get('display_name', 'Unknown'),
            'role': result.get('title', ''),
            'location': result.get('location', {}).get('display_name', ''),
            'salary_range': self._format_salary(
                result.get('salary_min'), result.get('salary_max')
            ),
            'job_description': result.get('description', ''),
            'source': source,
            'source_url': result.get('redirect_url', ''),
        }

    def run_all_searches(self):
        results = []
        for keyword in SEARCH_KEYWORDS:
            for raw in self.search(keyword, country='ie', where='Dublin'):
                parsed = self._parse_result(raw)
                if _should_include(parsed['role'], parsed['job_description']):
                    results.append(parsed)

            # Ireland-wide (catches Leinster/commutable roles listed without city)
            for raw in self.search(keyword, country='ie'):
                parsed = self._parse_result(raw)
                if _should_include(parsed['role'], parsed['job_description']):
                    results.append(parsed)

            # Remote on Adzuna Ireland
            for raw in self.search(keyword, country='ie', remote=True):
                parsed = self._parse_result(raw)
                if _should_include(parsed['role'], parsed['job_description']):
                    results.append(parsed)

            # Remote on Adzuna UK
            for raw in self.search(keyword, country='gb', remote=True):
                parsed = self._parse_result(raw)
                if _should_include(parsed['role'], parsed['job_description']):
                    results.append(parsed)

            # Remote on Adzuna Australia/Canada (English-speaking remote roles)
            for country in ('au', 'ca'):
                for raw in self.search(keyword, country=country, remote=True):
                    parsed = self._parse_result(raw)
                    if _should_include(parsed['role'], parsed['job_description']):
                        results.append(parsed)

        return results


class RSSSearcher:
    FEEDS = [
        # --- Irish boards (parameterised by keyword) ---
        {
            'url': 'https://ie.indeed.com/rss?q={keyword}&l=Dublin&sort=date',
            'source': 'rss_indeed',
            'location': 'Dublin, Ireland',
            'parameterised': True,
        },
        {
            'url': 'https://www.jobs.ie/JobsSearch/rss?q={keyword}&l=Dublin',
            'source': 'rss_indeed',
            'location': 'Dublin, Ireland',
            'parameterised': True,
        },
        # --- Global remote boards (full feed, filtered by title) ---
        {
            'url': 'https://weworkremotely.com/remote-jobs.rss',
            'source': 'rss_remote',
            'location': 'Remote',
            'parameterised': False,
        },
        {
            'url': 'https://remotive.com/remote-jobs/feed/',
            'source': 'rss_remote',
            'location': 'Remote',
            'parameterised': False,
        },
        {
            'url': 'https://remoteok.com/remote-jobs.rss',
            'source': 'rss_remote',
            'location': 'Remote',
            'parameterised': False,
        },
        {
            'url': 'https://remote.co/remote-jobs/feed/',
            'source': 'rss_remote',
            'location': 'Remote',
            'parameterised': False,
        },
        {
            'url': 'https://jobicy.com/?feed=job_feed',
            'source': 'rss_remote',
            'location': 'Remote',
            'parameterised': False,
        },
        {
            'url': 'https://www.workingnomads.com/feed',
            'source': 'rss_remote',
            'location': 'Remote',
            'parameterised': False,
        },
    ]

    @staticmethod
    def _strip_html(text):
        return re.sub(r'<[^>]+>', '', text or '').strip()

    def _fetch_raw(self, url):
        headers = {'User-Agent': 'Mozilla/5.0 JobTracker/1.0'}
        response = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        response.raise_for_status()
        return response.content

    def fetch_feed(self, url, source, location):
        try:
            content = self._fetch_raw(url)
            feed = feedparser.parse(content)
        except Exception:
            return []

        results = []
        for entry in feed.entries:
            title = entry.get('title', '')
            description = self._strip_html(entry.get('summary', ''))

            if not _should_include(title, description):
                continue

            parts = [p.strip() for p in title.split(' - ')]
            role = parts[0] if parts else title
            company = parts[1] if len(parts) >= 2 else 'Unknown'

            link = entry.get('link', '')
            if not link:
                continue

            results.append({
                'company': company,
                'role': role,
                'location': location,
                'salary_range': '',
                'job_description': description[:5000],
                'source': source,
                'source_url': link,
            })

        return results

    def run_all_searches(self):
        results = []
        for feed_config in self.FEEDS:
            if feed_config['parameterised']:
                for keyword in SEARCH_KEYWORDS:
                    url = feed_config['url'].format(
                        keyword=keyword.replace(' ', '+')
                    )
                    results.extend(
                        self.fetch_feed(url, feed_config['source'], feed_config['location'])
                    )
            else:
                results.extend(
                    self.fetch_feed(
                        feed_config['url'],
                        feed_config['source'],
                        feed_config['location'],
                    )
                )
        return results


def save_leads(job_dicts):
    created = skipped = 0
    for job in job_dicts:
        if not job.get('source_url') or not job.get('role'):
            skipped += 1
            continue
        _, was_created = JobLead.objects.get_or_create(
            source_url=job['source_url'],
            defaults={
                'company': job.get('company', 'Unknown'),
                'role': job['role'],
                'location': job.get('location', ''),
                'salary_range': job.get('salary_range', ''),
                'job_description': job.get('job_description', ''),
                'source': job.get('source', 'manual'),
            },
        )
        if was_created:
            created += 1
        else:
            skipped += 1
    return created, skipped
