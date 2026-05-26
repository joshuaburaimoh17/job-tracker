import html
import re


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
