import difflib
import json
import re
from datetime import date
from itertools import zip_longest
from pathlib import Path

import anthropic
from docx import Document
from django.conf import settings

# Exact section heading text as it appears in the CV
KNOWN_SECTIONS = frozenset([
    'Professional Summary',
    'Work Experience',
    'Projects',
    'Skills',
    'Education',
    'Achievements',
])


def _extract_section_text(doc, section_heading):
    """Return all paragraph text between section_heading and the next known section."""
    collecting = False
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if text == section_heading:
            collecting = True
            continue
        if collecting:
            if text in KNOWN_SECTIONS:
                break
            lines.append(text)
    return '\n'.join(lines)


def _extract_all_text(doc):
    return '\n'.join(p.text.strip() for p in doc.paragraphs if p.text.strip())


def _call_claude(original_summary, original_skills, job_description, role, company):
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    prompt = f"""You are helping a recent graduate tailor their CV for a specific job application.

JOB ROLE: {role}
COMPANY: {company}

JOB DESCRIPTION:
{job_description[:2500]}

CURRENT PROFESSIONAL SUMMARY:
{original_summary}

CURRENT SKILLS (each category is one line in "Category:  Skill1, Skill2" format):
{original_skills}

Instructions:
- Rewrite the summary to highlight experience most relevant to this specific role (3-4 confident sentences)
- Reorder and rewrite the skills lines to emphasise what matters for this role
- Do NOT invent skills or experience not already in the CV
- Keep each skills category on its own line using "Category:  Skill1, Skill2, ..." format with two spaces after the colon

Return ONLY valid JSON with no markdown fences:
{{"summary": "...", "skills": "Business Analysis:  ...\\nTechnical:  ...\\nTools & Platforms:  ...\\nSoft Skills:  ...", "changes_made": "..."}}"""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1024,
        messages=[{'role': 'user', 'content': prompt}],
    )

    text = message.content[0].text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE).strip()
    return json.loads(text)


def _replace_para_text(para, new_text):
    """Replace paragraph text while preserving the first run's formatting."""
    if not para.runs:
        return
    para.runs[0].text = new_text
    for run in para.runs[1:]:
        run.text = ''


def _save_tailored_docx(doc_path, tailored_data, lead):
    doc = Document(str(doc_path))

    in_summary = False
    in_skills = False
    summary_written = False
    skill_lines = [l for l in tailored_data['skills'].splitlines() if l.strip()]
    skill_idx = 0

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Section transitions — keep heading paragraphs unchanged
        if text == 'Professional Summary':
            in_summary, in_skills = True, False
            continue
        if text == 'Skills':
            in_summary, in_skills = False, True
            continue
        if text in KNOWN_SECTIONS:
            in_summary, in_skills = False, False
            continue

        if in_summary and not summary_written:
            _replace_para_text(para, tailored_data['summary'])
            summary_written = True
        elif in_summary:
            _replace_para_text(para, '')
        elif in_skills and skill_idx < len(skill_lines):
            _replace_para_text(para, skill_lines[skill_idx])
            skill_idx += 1
        elif in_skills and skill_idx >= len(skill_lines):
            _replace_para_text(para, '')

    company_slug = re.sub(r'[^\w]', '_', lead.company)[:25]
    role_slug = re.sub(r'[^\w]', '_', lead.role)[:25]
    filename = f"{company_slug}_{role_slug}_{date.today().isoformat()}.docx"

    out_dir = Path(settings.CV_APPLICATIONS_PATH)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    doc.save(str(out_path))
    return out_path


def compute_diff(original_text, tailored_text):
    """
    Return list of ((orig_line, orig_status), (tail_line, tail_status)) tuples
    suitable for rendering a side-by-side diff in a template.
    Status values: 'same', 'removed', 'added'
    """
    orig_lines = [l for l in original_text.splitlines() if l.strip()]
    tail_lines = [l for l in tailored_text.splitlines() if l.strip()]

    matcher = difflib.SequenceMatcher(None, orig_lines, tail_lines, autojunk=False)
    orig_rows, tail_rows = [], []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for line in orig_lines[i1:i2]:
                orig_rows.append((line, 'same'))
                tail_rows.append((line, 'same'))
        elif tag == 'replace':
            for line in orig_lines[i1:i2]:
                orig_rows.append((line, 'removed'))
            for line in tail_lines[j1:j2]:
                tail_rows.append((line, 'added'))
        elif tag == 'delete':
            for line in orig_lines[i1:i2]:
                orig_rows.append((line, 'removed'))
        elif tag == 'insert':
            for line in tail_lines[j1:j2]:
                tail_rows.append((line, 'added'))

    return list(zip_longest(orig_rows, tail_rows, fillvalue=('', 'same')))


def tailor_cv_for_lead(lead):
    """
    Main entry point. Reads base CV, calls Claude, saves tailored .docx.
    Returns dict with text content and cv_path.
    """
    doc_path = settings.CV_BASE_PATH
    doc = Document(str(doc_path))

    original_summary = _extract_section_text(doc, 'Professional Summary')
    original_skills = _extract_section_text(doc, 'Skills')
    original_full = _extract_all_text(doc)

    tailored_data = _call_claude(
        original_summary,
        original_skills,
        lead.job_description,
        lead.role,
        lead.company,
    )

    cv_path = _save_tailored_docx(str(doc_path), tailored_data, lead)

    # Build full tailored text by substituting changed sections
    tailored_full = original_full.replace(original_summary, tailored_data['summary'], 1)
    tailored_full = tailored_full.replace(original_skills, tailored_data['skills'], 1)

    return {
        'original_text': original_full,
        'tailored_text': tailored_full,
        'changes_made': tailored_data.get('changes_made', ''),
        'cv_path': str(cv_path),
    }
