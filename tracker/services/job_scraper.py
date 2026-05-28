import httpx
from bs4 import BeautifulSoup

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-IE,en;q=0.9',
}


def scrape_job_url(url: str) -> dict:
    try:
        r = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=15)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"HTTP {e.response.status_code} fetching {url}") from e
    except httpx.RequestError as e:
        raise RuntimeError(f"Network error fetching {url}: {e}") from e

    soup = BeautifulSoup(r.text, 'html.parser')

    role = _extract_role(soup)
    company = _extract_company(soup)
    description = _extract_description(soup)

    if not role:
        raise RuntimeError(f"Could not extract job title from {url}")
    if not description:
        raise RuntimeError(f"Could not extract job description from {url}")

    return {
        'role': role.strip(),
        'company': (company or '').strip(),
        'job_description': description.strip(),
    }


def _extract_role(soup: BeautifulSoup) -> str | None:
    for selector in [
        'h1[data-testid="jobsearch-JobInfoHeader-title"]',
        'h1.jobsearch-JobInfoHeader-title',
        '[class*="jobTitle"] h1',
        'h1',
    ]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(strip=True)
    return None


def _extract_company(soup: BeautifulSoup) -> str:
    for selector in [
        '[data-testid="inlineHeader-companyName"]',
        '[data-testid="jobsearch-JobInfoHeader-companyName"]',
        '[class*="companyName"]',
        '[class*="company-name"]',
    ]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(strip=True)
    return ''


def _extract_description(soup: BeautifulSoup) -> str:
    for selector in [
        '#jobDescriptionText',
        '[data-testid="jobsearch-jobDescriptionText"]',
        '.jobsearch-jobDescriptionText',
        '[class*="jobDescription"]',
        'article',
    ]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(separator='\n', strip=True)
    main = soup.find('main')
    if main:
        return main.get_text(separator='\n', strip=True)
    return ''
