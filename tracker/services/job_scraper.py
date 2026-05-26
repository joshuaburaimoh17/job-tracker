import re
import httpx
import anthropic
from bs4 import BeautifulSoup
from django.conf import settings
from .utils import clean_job_description


_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

_JD_SELECTORS = [
    '[class*="job-description"]',
    '[class*="jobDescription"]',
    '[class*="job_description"]',
    '[id*="job-description"]',
    '[id*="jobDescription"]',
    '[class*="description"]',
    'article',
    'main',
]

_STRIP_TAGS = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript', 'iframe'}


def _fetch_page(url: str) -> str:
    resp = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=15)
    resp.raise_for_status()
    return resp.text


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, 'lxml')
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    container = None
    for selector in _JD_SELECTORS:
        container = soup.select_one(selector)
        if container:
            break
    if container is None:
        container = soup.body or soup

    text = container.get_text(separator='\n')
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    text = '\n'.join(lines)
    # collapse runs of 3+ blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text[:6000]


def _call_claude(page_text: str, url: str) -> dict:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = f"""Extract job posting details from the page text below and return ONLY valid JSON with these keys:
- company (string, employer name)
- role (string, job title)
- location (string, city/country or "Remote" — empty string if not found)
- salary_range (string, e.g. "€30,000 – €40,000" — empty string if not stated)
- job_description (string, full job description including responsibilities and requirements — preserve as much detail as possible)

Source URL: {url}

Page text:
{page_text}

Return ONLY the JSON object, no markdown fences, no extra text."""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        messages=[{'role': 'user', 'content': prompt}],
    )
    raw = message.content[0].text.strip()
    # strip markdown fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'```\s*$', '', raw, flags=re.MULTILINE)
    import json
    return json.loads(raw.strip())


def scrape_job_url(url: str) -> dict:
    """Fetch a job posting URL and return extracted fields via Claude.

    Returns dict with keys: company, role, location, salary_range, job_description.
    Raises ValueError if the page content is too short to be a real job posting.
    Raises httpx.HTTPError on network failures.
    """
    html = _fetch_page(url)
    page_text = _extract_text(html)
    if len(page_text) < 200:
        raise ValueError(f'Page content too short ({len(page_text)} chars) — may be a login wall or redirect.')
    data = _call_claude(page_text, url)
    # Ensure all expected keys exist
    for key in ('company', 'role', 'location', 'salary_range', 'job_description'):
        data.setdefault(key, '')
    data['job_description'] = clean_job_description(data['job_description'])
    return data
