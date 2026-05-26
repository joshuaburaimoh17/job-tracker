import html
import re

# On-site language that contradicts a "Remote" lead.
_ONSITE_RE = re.compile(
    r'\bon[-\s]?site\b'
    r'|\bin[-\s]?office\b'
    r'|office[-\s]based'
    r'|must\s+(be\s+)?(in|at|work\s+from)\s+(the\s+)?office'
    r'|not\s+remote'
    r'|no\s+remote\s+work',
    re.I,
)

# Non-Irish cities that shouldn't appear in the location field of a Dublin lead.
_NON_IE_LOCATION_RE = re.compile(
    r'\b(london|manchester|edinburgh|glasgow|birmingham|leeds|bristol|'
    r'liverpool|cardiff|newcastle|amsterdam|berlin|paris|new york|san francisco)\b',
    re.I,
)


def has_location_mismatch(lead) -> bool:
    """Return True if the lead's location signals conflict with its source category."""
    desc = (lead.job_description or '').lower()
    loc = (lead.location or '').lower()

    # Remote-sourced lead that mentions on-site requirements in the description.
    if lead.source == 'rss_remote' or 'remote' in loc:
        return bool(desc and _ONSITE_RE.search(desc))

    # Adzuna lead whose location field shows a non-Irish city.
    # (The Dublin search uses where='Dublin' so it's fine; the remote search doesn't.)
    if lead.source == 'adzuna' and loc and _NON_IE_LOCATION_RE.search(loc):
        return True

    return False


def clean_job_description(text: str) -> str:
    """Decode HTML entities, strip markdown symbols, normalise whitespace."""
    if not text:
        return text

    # Decode HTML entities: &#160; → ' ', &#8217; → ', &amp; → &, etc.
    text = html.unescape(text)

    # Strip any residual HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # Convert smart quotes and common unicode punctuation to plain ASCII
    text = (text
        .replace(' ', ' ')   # non-breaking space
        .replace('​', '')    # zero-width space
        .replace('’', "'")   # right single quote
        .replace('‘', "'")   # left single quote
        .replace('“', '"')   # left double quote
        .replace('”', '"')   # right double quote
        .replace('–', '-')   # en dash
        .replace('—', ' - ') # em dash
        .replace('•', '-')   # bullet •
        .replace('·', '-')   # middle dot ·
    )

    # Remove markdown bold/italic (**text** → text, *text* → text, __x__ → x, _x_ → x)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'\*(.+?)\*',     r'\1', text, flags=re.DOTALL)
    text = re.sub(r'__(.+?)__',     r'\1', text, flags=re.DOTALL)
    text = re.sub(r'_(.+?)_',       r'\1', text, flags=re.DOTALL)

    # Remove markdown headers (## Heading → Heading)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove markdown horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Collapse multiple spaces/tabs on the same line to one space
    text = re.sub(r'[ \t]+', ' ', text)

    # Strip trailing space from each line
    text = '\n'.join(line.strip() for line in text.splitlines())

    # Collapse 3+ blank lines down to 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
