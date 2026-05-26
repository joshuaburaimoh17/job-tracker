import datetime
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse, resolve
from django.db import IntegrityError
from .models import Application, JobLead
from . import views
from .services.job_search import AdzunaSearcher, RSSSearcher, save_leads


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class JobLeadModelTest(TestCase):

    def setUp(self):
        self.lead = JobLead.objects.create(
            company='Acme Corp',
            role='Junior Developer',
            location='Dublin',
            job_description='We are looking for a Junior Developer.',
            source='manual',
            source_url='https://example.com/jobs/1',
        )

    def test_str(self):
        self.assertEqual(str(self.lead), 'Junior Developer at Acme Corp')

    def test_default_status_is_new(self):
        self.assertEqual(self.lead.status, 'new')

    def test_ordering_most_recent_first(self):
        lead2 = JobLead.objects.create(
            company='Beta Ltd',
            role='Graduate BA',
            job_description='Looking for a Graduate BA.',
            source='adzuna',
            source_url='https://example.com/jobs/2',
        )
        leads = list(JobLead.objects.all())
        self.assertEqual(leads[0], lead2)

    def test_source_url_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            JobLead.objects.create(
                company='Dupe Corp',
                role='Junior Developer',
                job_description='Duplicate URL test.',
                source='manual',
                source_url='https://example.com/jobs/1',
            )

    def test_optional_fields_default_blank(self):
        self.assertEqual(self.lead.salary_range, '')
        self.assertEqual(self.lead.cv_path, '')
        self.assertIsNone(self.lead.application)


class ApplicationModelExtensionsTest(TestCase):

    def test_job_description_and_cv_path_fields(self):
        app = Application.objects.create(
            company='Acme',
            role='Junior Developer',
            date_applied=datetime.date.today(),
            job_description='Some JD text.',
            cv_path='CVs/Applications/Acme_Junior_Developer_2026-05-25.docx',
        )
        self.assertEqual(app.job_description, 'Some JD text.')
        self.assertIn('Acme', app.cv_path)

    def test_job_description_defaults_null(self):
        app = Application.objects.create(
            company='Beta',
            role='Graduate BA',
            date_applied=datetime.date.today(),
        )
        self.assertIsNone(app.job_description)
        self.assertEqual(app.cv_path, '')


# ---------------------------------------------------------------------------
# View tests
# ---------------------------------------------------------------------------

class JobQueueViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.lead = JobLead.objects.create(
            company='Acme Corp',
            role='Junior Developer',
            job_description='We are looking for a Junior Developer.',
            source='manual',
            source_url='https://example.com/jobs/1',
        )

    def test_queue_returns_200(self):
        response = self.client.get(reverse('job_queue'))
        self.assertEqual(response.status_code, 200)

    def test_queue_shows_new_leads_by_default(self):
        response = self.client.get(reverse('job_queue'))
        self.assertContains(response, 'Acme Corp')

    def test_queue_filter_dismissed_excludes_new_lead(self):
        response = self.client.get(reverse('job_queue') + '?status=dismissed')
        self.assertNotContains(response, 'Acme Corp')

    def test_queue_uses_correct_template(self):
        response = self.client.get(reverse('job_queue'))
        self.assertTemplateUsed(response, 'tracker/job_queue.html')

    def test_queue_context_has_leads(self):
        response = self.client.get(reverse('job_queue'))
        self.assertIn('leads', response.context)

    def test_queue_context_has_new_count(self):
        response = self.client.get(reverse('job_queue'))
        self.assertEqual(response.context['new_count'], 1)


class JobLeadDetailViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.lead = JobLead.objects.create(
            company='Beta Ltd',
            role='Graduate BA',
            job_description='Looking for a Graduate BA to join our team.',
            source='adzuna',
            source_url='https://example.com/jobs/2',
        )

    def test_detail_returns_200(self):
        response = self.client.get(reverse('job_lead_detail', args=[self.lead.pk]))
        self.assertEqual(response.status_code, 200)

    def test_detail_shows_company_and_role(self):
        response = self.client.get(reverse('job_lead_detail', args=[self.lead.pk]))
        self.assertContains(response, 'Beta Ltd')
        self.assertContains(response, 'Graduate BA')

    def test_detail_shows_job_description(self):
        response = self.client.get(reverse('job_lead_detail', args=[self.lead.pk]))
        self.assertContains(response, 'Looking for a Graduate BA')

    def test_detail_returns_404_for_bad_pk(self):
        response = self.client.get(reverse('job_lead_detail', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_detail_uses_correct_template(self):
        response = self.client.get(reverse('job_lead_detail', args=[self.lead.pk]))
        self.assertTemplateUsed(response, 'tracker/job_lead_detail.html')


class DismissLeadViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.lead = JobLead.objects.create(
            company='Gamma Inc',
            role='Technical Analyst',
            job_description='Technical Analyst role.',
            source='rss_indeed',
            source_url='https://example.com/jobs/3',
        )

    def test_dismiss_updates_status_to_dismissed(self):
        self.client.post(reverse('dismiss_lead', args=[self.lead.pk]))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, 'dismissed')

    def test_dismiss_redirects_to_queue(self):
        response = self.client.post(reverse('dismiss_lead', args=[self.lead.pk]))
        self.assertRedirects(response, reverse('job_queue'))

    def test_dismiss_get_does_not_change_status(self):
        self.client.get(reverse('dismiss_lead', args=[self.lead.pk]))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, 'new')

    def test_dismiss_returns_404_for_bad_pk(self):
        response = self.client.post(reverse('dismiss_lead', args=[9999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# URL resolution tests
# ---------------------------------------------------------------------------

class URLResolutionTest(TestCase):

    def test_job_queue_url_resolves(self):
        url = reverse('job_queue')
        self.assertEqual(url, '/queue/')
        self.assertEqual(resolve(url).func, views.job_queue)

    def test_job_lead_detail_url_resolves(self):
        url = reverse('job_lead_detail', args=[42])
        self.assertEqual(url, '/queue/42/')
        self.assertEqual(resolve(url).func, views.job_lead_detail)

    def test_dismiss_lead_url_resolves(self):
        url = reverse('dismiss_lead', args=[42])
        self.assertEqual(url, '/queue/42/dismiss/')
        self.assertEqual(resolve(url).func, views.dismiss_lead)


# ---------------------------------------------------------------------------
# Phase 2 — Job search service tests
# ---------------------------------------------------------------------------

SAMPLE_ADZUNA_RESULT = {
    'title': 'Junior Developer',
    'company': {'display_name': 'Acme Corp'},
    'location': {'display_name': 'Dublin, County Dublin'},
    'salary_min': 28000,
    'salary_max': 35000,
    'description': 'We are looking for a Junior Developer to join our team.',
    'redirect_url': 'https://www.adzuna.ie/details/abc123',
}

SAMPLE_RSS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Indeed Jobs</title>
    <item>
      <title>Junior Developer - Acme Corp - Dublin</title>
      <link>https://ie.indeed.com/viewjob?jk=abc123</link>
      <description>We are hiring a Junior Developer for our Dublin office.</description>
    </item>
    <item>
      <title>Senior Manager - XYZ Corp - Cork</title>
      <link>https://ie.indeed.com/viewjob?jk=xyz999</link>
      <description>Senior management role in Cork.</description>
    </item>
    <item>
      <title>Graduate Business Analyst - Tech Co - Remote</title>
      <link>https://ie.indeed.com/viewjob?jk=gba456</link>
      <description>Graduate BA role, fully remote.</description>
    </item>
  </channel>
</rss>"""


class AdzunaSearcherParseTest(TestCase):

    def setUp(self):
        self.searcher = AdzunaSearcher()

    def test_parse_result_extracts_company_and_role(self):
        result = self.searcher._parse_result(SAMPLE_ADZUNA_RESULT)
        self.assertEqual(result['company'], 'Acme Corp')
        self.assertEqual(result['role'], 'Junior Developer')

    def test_parse_result_extracts_location(self):
        result = self.searcher._parse_result(SAMPLE_ADZUNA_RESULT)
        self.assertEqual(result['location'], 'Dublin, County Dublin')

    def test_parse_result_formats_salary_range(self):
        result = self.searcher._parse_result(SAMPLE_ADZUNA_RESULT)
        self.assertEqual(result['salary_range'], '€28,000 – €35,000')

    def test_parse_result_salary_min_only(self):
        partial = {**SAMPLE_ADZUNA_RESULT, 'salary_max': None}
        result = self.searcher._parse_result(partial)
        self.assertEqual(result['salary_range'], 'From €28,000')

    def test_parse_result_no_salary(self):
        partial = {**SAMPLE_ADZUNA_RESULT, 'salary_min': None, 'salary_max': None}
        result = self.searcher._parse_result(partial)
        self.assertEqual(result['salary_range'], '')

    def test_parse_result_source_url_is_redirect_url(self):
        result = self.searcher._parse_result(SAMPLE_ADZUNA_RESULT)
        self.assertEqual(result['source_url'], 'https://www.adzuna.ie/details/abc123')

    def test_parse_result_source_defaults_to_adzuna(self):
        result = self.searcher._parse_result(SAMPLE_ADZUNA_RESULT)
        self.assertEqual(result['source'], 'adzuna')


class AdzunaSearcherHTTPTest(TestCase):

    def setUp(self):
        self.searcher = AdzunaSearcher()

    @patch('tracker.services.job_search.httpx.get')
    def test_search_returns_results_on_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'results': [SAMPLE_ADZUNA_RESULT]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = self.searcher.search('Junior Developer', country='ie', where='Dublin')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Junior Developer')

    @patch('tracker.services.job_search.httpx.get')
    def test_search_returns_empty_list_on_http_error(self, mock_get):
        import httpx as httpx_module
        mock_get.side_effect = httpx_module.HTTPError('timeout')
        results = self.searcher.search('Junior Developer', country='ie')
        self.assertEqual(results, [])

    @patch('tracker.services.job_search.httpx.get')
    def test_search_appends_remote_to_keyword_when_flagged(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'results': []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        self.searcher.search('Junior Developer', remote=True)
        call_kwargs = mock_get.call_args
        self.assertIn('remote', call_kwargs[1]['params']['what'])


class RSSSearcherTest(TestCase):

    def setUp(self):
        self.searcher = RSSSearcher()

    def test_matches_keywords_true_for_junior_developer(self):
        from tracker.services.job_search import _should_include
        self.assertTrue(_should_include('Junior Developer'))

    def test_matches_keywords_true_for_graduate_ba(self):
        from tracker.services.job_search import _should_include
        self.assertTrue(_should_include('Graduate Business Analyst'))

    def test_matches_keywords_false_for_senior_manager(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Senior Manager'))

    def test_matches_keywords_case_insensitive(self):
        from tracker.services.job_search import _should_include
        self.assertTrue(_should_include('JUNIOR DEVELOPER'))

    # --- tighter filter tests ---
    def test_blocks_senior_role(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Senior Business Analyst'))

    def test_blocks_ios_developer(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('iOS Developer'))

    def test_blocks_android_developer(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Junior Android Developer'))

    def test_blocks_devops_engineer(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Junior DevOps Engineer'))

    def test_blocks_ux_designer(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('UX Designer'))

    def test_blocks_dotnet_without_junior(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Business Analyst .NET Developer'))

    def test_allows_junior_dotnet(self):
        from tracker.services.job_search import _should_include
        self.assertTrue(_should_include('Junior .NET Developer'))

    def test_blocks_three_plus_years_experience(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Junior Developer', '3+ years of experience required'))

    def test_blocks_two_plus_years_experience(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Junior Developer', '2+ years of experience required'))

    def test_blocks_minimum_two_years(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Junior Business Analyst', 'Minimum 2 years in a similar role'))

    def test_blocks_at_least_two_years(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Junior Developer', 'At least 2 years of experience'))

    def test_allows_one_year_experience(self):
        from tracker.services.job_search import _should_include
        self.assertTrue(_should_include('Junior Developer', '1 year of experience preferred'))

    def test_allows_generic_experienced_without_years(self):
        from tracker.services.job_search import _should_include
        self.assertTrue(_should_include('Junior Developer', 'We are looking for an experienced candidate'))

    def test_blocks_no_graduates(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Junior Developer', 'No graduates please'))

    def test_blocks_experienced_candidates_only(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Junior Business Analyst', 'Experienced candidates only'))

    def test_blocks_not_suitable_for_juniors(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Junior Developer', 'This role is not suitable for juniors'))

    def test_blocks_two_senior_infra_skills(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Junior Developer', 'Must have Kubernetes and Terraform experience'))

    def test_allows_single_infra_skill(self):
        from tracker.services.job_search import _should_include
        self.assertTrue(_should_include('Junior Developer', 'Familiarity with Kubernetes is a plus'))

    def test_allows_degree_required(self):
        from tracker.services.job_search import _should_include
        self.assertTrue(_should_include('Junior Developer', 'A degree in Computer Science or related field is required'))

    def test_allows_long_skills_list_without_experience_requirement(self):
        from tracker.services.job_search import _should_include
        desc = 'Skills: Python, SQL, Excel, Power BI, Tableau, Git, Agile, Scrum, JIRA, Confluence'
        self.assertTrue(_should_include('Graduate Business Analyst', desc))

    def test_blocks_us_only_role(self):
        from tracker.services.job_search import _should_include
        self.assertFalse(_should_include('Junior Developer', 'Must be based in the US'))

    def test_allows_data_analyst(self):
        from tracker.services.job_search import _should_include
        self.assertTrue(_should_include('Graduate Data Analyst'))

    def test_allows_full_stack(self):
        from tracker.services.job_search import _should_include
        self.assertTrue(_should_include('Junior Full Stack Developer'))

    def test_allows_backend(self):
        from tracker.services.job_search import _should_include
        self.assertTrue(_should_include('Junior Backend Developer'))

    def test_strip_html_removes_tags(self):
        self.assertEqual(
            self.searcher._strip_html('<p>Hello <b>world</b></p>'),
            'Hello world'
        )

    @patch('tracker.services.job_search.httpx.get')
    def test_fetch_feed_filters_to_matching_titles_only(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = SAMPLE_RSS_XML
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = self.searcher.fetch_feed('https://example.com/rss', 'rss_indeed', 'Dublin, Ireland')
        # Only "Junior Developer" and "Graduate Business Analyst" match; "Senior Manager" should be filtered
        titles = [r['role'] for r in results]
        self.assertIn('Junior Developer', titles)
        self.assertIn('Graduate Business Analyst', titles)
        self.assertNotIn('Senior Manager', titles)

    @patch('tracker.services.job_search.httpx.get')
    def test_fetch_feed_returns_empty_on_http_error(self, mock_get):
        import httpx as httpx_module
        mock_get.side_effect = httpx_module.HTTPError('connection failed')
        results = self.searcher.fetch_feed('https://example.com/rss', 'rss_indeed', 'Dublin')
        self.assertEqual(results, [])

    @patch('tracker.services.job_search.httpx.get')
    def test_fetch_feed_parses_company_from_title(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = SAMPLE_RSS_XML
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = self.searcher.fetch_feed('https://example.com/rss', 'rss_indeed', 'Dublin, Ireland')
        junior_dev = next(r for r in results if r['role'] == 'Junior Developer')
        self.assertEqual(junior_dev['company'], 'Acme Corp')

    @patch('tracker.services.job_search.httpx.get')
    def test_fetch_feed_skips_entries_without_link(self, mock_get):
        no_link_xml = b"""<?xml version="1.0"?>
        <rss version="2.0"><channel>
          <item><title>Junior Developer - Acme</title><description>test</description></item>
        </channel></rss>"""
        mock_response = MagicMock()
        mock_response.content = no_link_xml
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        results = self.searcher.fetch_feed('https://example.com/rss', 'rss_indeed', 'Dublin')
        self.assertEqual(results, [])


class SaveLeadsTest(TestCase):

    def _make_job(self, url='https://example.com/job/1', role='Junior Developer'):
        return {
            'company': 'Acme Corp',
            'role': role,
            'location': 'Dublin',
            'salary_range': '€28,000 – €35,000',
            'job_description': 'A great role.',
            'source': 'adzuna',
            'source_url': url,
        }

    def test_save_leads_creates_new_entry(self):
        created, skipped = save_leads([self._make_job()])
        self.assertEqual(created, 1)
        self.assertEqual(JobLead.objects.count(), 1)

    def test_save_leads_skips_duplicate_url(self):
        save_leads([self._make_job()])
        created, skipped = save_leads([self._make_job()])
        self.assertEqual(created, 0)
        self.assertEqual(skipped, 1)
        self.assertEqual(JobLead.objects.count(), 1)

    def test_save_leads_skips_entry_with_no_url(self):
        job = self._make_job()
        job['source_url'] = ''
        created, skipped = save_leads([job])
        self.assertEqual(created, 0)
        self.assertEqual(skipped, 1)

    def test_save_leads_skips_entry_with_no_role(self):
        job = self._make_job()
        job['role'] = ''
        created, skipped = save_leads([job])
        self.assertEqual(created, 0)
        self.assertEqual(skipped, 1)

    def test_save_leads_persists_all_fields(self):
        save_leads([self._make_job()])
        lead = JobLead.objects.first()
        self.assertEqual(lead.company, 'Acme Corp')
        self.assertEqual(lead.location, 'Dublin')
        self.assertEqual(lead.salary_range, '€28,000 – €35,000')
        self.assertEqual(lead.source, 'adzuna')

    def test_save_leads_handles_mixed_valid_and_invalid(self):
        jobs = [
            self._make_job('https://example.com/1'),
            {'role': '', 'source_url': ''},  # invalid
            self._make_job('https://example.com/2'),
        ]
        created, skipped = save_leads(jobs)
        self.assertEqual(created, 2)
        self.assertEqual(skipped, 1)


class SearchJobsCommandTest(TestCase):

    @patch('tracker.management.commands.search_jobs.RSSSearcher')
    @patch('tracker.management.commands.search_jobs.AdzunaSearcher')
    def test_command_saves_leads_from_both_sources(self, MockAdzuna, MockRSS):
        MockAdzuna.return_value.run_all_searches.return_value = [{
            'company': 'Adzuna Co', 'role': 'Junior Developer',
            'location': 'Dublin', 'salary_range': '', 'job_description': 'JD',
            'source': 'adzuna', 'source_url': 'https://adzuna.ie/1',
        }]
        MockRSS.return_value.run_all_searches.return_value = [{
            'company': 'RSS Co', 'role': 'Graduate BA',
            'location': 'Remote', 'salary_range': '', 'job_description': 'JD',
            'source': 'rss_indeed', 'source_url': 'https://indeed.ie/1',
        }]

        from django.core.management import call_command
        call_command('search_jobs')
        self.assertEqual(JobLead.objects.count(), 2)

    @patch('tracker.management.commands.search_jobs.RSSSearcher')
    @patch('tracker.management.commands.search_jobs.AdzunaSearcher')
    def test_command_does_not_duplicate_existing_leads(self, MockAdzuna, MockRSS):
        JobLead.objects.create(
            company='Existing Co', role='Junior Developer',
            job_description='already here', source='adzuna',
            source_url='https://adzuna.ie/existing',
        )
        MockAdzuna.return_value.run_all_searches.return_value = [{
            'company': 'Existing Co', 'role': 'Junior Developer',
            'location': 'Dublin', 'salary_range': '', 'job_description': 'JD',
            'source': 'adzuna', 'source_url': 'https://adzuna.ie/existing',
        }]
        MockRSS.return_value.run_all_searches.return_value = []

        from django.core.management import call_command
        call_command('search_jobs')
        self.assertEqual(JobLead.objects.count(), 1)


# ---------------------------------------------------------------------------
# Phase 3 — CV tailoring service tests
# ---------------------------------------------------------------------------

def _make_mock_doc(paragraphs):
    """
    Build a minimal mock Document from a list of (text, bold) tuples.
    Enough to satisfy _extract_section_text and _save_tailored_docx.
    """
    class MockRun:
        def __init__(self, text, bold):
            self.text = text
            self.bold = bold

    class MockParagraph:
        def __init__(self, text, bold=False):
            self._text = text
            self.runs = [MockRun(text, bold)] if text else []

        @property
        def text(self):
            return self._text

        @property
        def style(self):
            class _S:
                name = 'Normal'
            return _S()

    class MockDoc:
        def __init__(self, paras):
            self.paragraphs = [MockParagraph(t, b) for t, b in paras]

    return MockDoc(paragraphs)


MOCK_CV_PARAGRAPHS = [
    ('Joshua Buraimoh', True),
    ('Balbriggan, Dublin | 087 446 2580', False),
    ('', False),
    ('Professional Summary', True),
    ('Final-year Computing for Business graduate with hands-on BA experience.', False),
    ('', False),
    ('Work Experience', True),
    ('Business Analyst Intern  |  AIG Dublin  |  February 2025', True),
    ('Supported regulatory compliance for the project.', False),
    ('', False),
    ('Skills', True),
    ('Business Analysis:  Requirements gathering, BRD documentation', True),
    ('Technical:  Python, Django, SQL, JavaScript', True),
    ('Tools & Platforms:  Git, GitHub, VS Code', True),
    ('Soft Skills:  Analytical thinking, communication', True),
    ('', False),
    ('Education', True),
    ('B.Sc. Computing for Business  |  DCU', True),
]

MOCK_CLAUDE_RESPONSE = {
    'summary': 'Results-driven graduate with BA and technical skills aligned to this role.',
    'skills': (
        'Business Analysis:  Process mapping, stakeholder engagement, BRD documentation\n'
        'Technical:  Python, Django, SQL, JavaScript, data analysis\n'
        'Tools & Platforms:  Git, GitHub, Microsoft Office, VS Code\n'
        'Soft Skills:  Communication, analytical thinking, problem-solving'
    ),
    'changes_made': 'Emphasised stakeholder engagement and data analysis keywords from JD.',
}


class ExtractSectionTextTest(TestCase):

    def setUp(self):
        self.doc = _make_mock_doc(MOCK_CV_PARAGRAPHS)

    def test_extracts_summary_text(self):
        from tracker.services.cv_tailor import _extract_section_text
        text = _extract_section_text(self.doc, 'Professional Summary')
        self.assertIn('Final-year Computing for Business', text)

    def test_summary_stops_before_next_section(self):
        from tracker.services.cv_tailor import _extract_section_text
        text = _extract_section_text(self.doc, 'Professional Summary')
        self.assertNotIn('Business Analyst Intern', text)
        self.assertNotIn('Work Experience', text)

    def test_extracts_skills_text(self):
        from tracker.services.cv_tailor import _extract_section_text
        text = _extract_section_text(self.doc, 'Skills')
        self.assertIn('Business Analysis:', text)
        self.assertIn('Technical:', text)

    def test_skills_stops_before_education(self):
        from tracker.services.cv_tailor import _extract_section_text
        text = _extract_section_text(self.doc, 'Skills')
        self.assertNotIn('B.Sc. Computing for Business', text)

    def test_returns_empty_string_for_unknown_section(self):
        from tracker.services.cv_tailor import _extract_section_text
        text = _extract_section_text(self.doc, 'Nonexistent Section')
        self.assertEqual(text, '')


class ComputeDiffTest(TestCase):

    def test_identical_texts_all_same(self):
        from tracker.services.cv_tailor import compute_diff
        rows = compute_diff('line one\nline two', 'line one\nline two')
        statuses = {s for _, (_, s) in rows}
        self.assertNotIn('removed', statuses)
        self.assertNotIn('added', statuses)

    def test_changed_line_marked_removed_and_added(self):
        from tracker.services.cv_tailor import compute_diff
        rows = compute_diff('old summary text', 'new summary text')
        orig_statuses = [s for (_, s), _ in rows if _[0] or s != 'same']
        tail_statuses = [s for _, (_, s) in rows if _[0] or s != 'same']
        self.assertIn('removed', orig_statuses)
        self.assertIn('added', tail_statuses)

    def test_returns_list_of_tuples(self):
        from tracker.services.cv_tailor import compute_diff
        rows = compute_diff('a\nb\nc', 'a\nX\nc')
        self.assertIsInstance(rows, list)
        self.assertIsInstance(rows[0], tuple)
        self.assertEqual(len(rows[0]), 2)  # (orig_pair, tail_pair)


class TailorCVViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.lead = JobLead.objects.create(
            company='Acme Corp',
            role='Junior Developer',
            job_description='Looking for a Junior Developer with Python skills.',
            source='adzuna',
            source_url='https://example.com/jobs/cv-test',
        )

    @patch('tracker.services.cv_tailor.tailor_cv_for_lead')
    def test_tailor_cv_post_updates_lead(self, mock_tailor):
        mock_tailor.return_value = {
            'original_text': 'Original CV text',
            'tailored_text': 'Tailored CV text',
            'cv_path': '/CVs/Applications/test.docx',
            'changes_made': 'Updated summary.',
        }
        self.client.post(reverse('tailor_cv', args=[self.lead.pk]))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.cv_original_text, 'Original CV text')
        self.assertEqual(self.lead.cv_tailored_text, 'Tailored CV text')
        self.assertEqual(self.lead.cv_path, '/CVs/Applications/test.docx')

    @patch('tracker.services.cv_tailor.tailor_cv_for_lead')
    def test_tailor_cv_post_redirects_to_detail(self, mock_tailor):
        mock_tailor.return_value = {
            'original_text': 'orig', 'tailored_text': 'tail',
            'cv_path': '/some/path.docx', 'changes_made': '',
        }
        response = self.client.post(reverse('tailor_cv', args=[self.lead.pk]))
        self.assertRedirects(response, reverse('job_lead_detail', args=[self.lead.pk]))

    @patch('tracker.services.cv_tailor.tailor_cv_for_lead')
    def test_tailor_cv_service_error_shows_message(self, mock_tailor):
        mock_tailor.side_effect = Exception('Claude API error')
        response = self.client.post(
            reverse('tailor_cv', args=[self.lead.pk]), follow=True
        )
        self.assertContains(response, 'CV tailoring failed')

    def test_tailor_cv_get_redirects(self):
        response = self.client.get(reverse('tailor_cv', args=[self.lead.pk]))
        # GET is a no-op — still redirects to detail
        self.assertRedirects(response, reverse('job_lead_detail', args=[self.lead.pk]))

    def test_tailor_cv_404_for_bad_pk(self):
        response = self.client.post(reverse('tailor_cv', args=[9999]))
        self.assertEqual(response.status_code, 404)


class MarkReadyViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.lead = JobLead.objects.create(
            company='Beta Ltd',
            role='Graduate BA',
            job_description='BA role.',
            source='manual',
            source_url='https://example.com/jobs/ready-test',
        )

    def test_mark_ready_sets_status(self):
        self.client.post(reverse('mark_ready', args=[self.lead.pk]))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, 'ready')

    def test_mark_ready_redirects_to_detail(self):
        response = self.client.post(reverse('mark_ready', args=[self.lead.pk]))
        self.assertRedirects(response, reverse('job_lead_detail', args=[self.lead.pk]))

    def test_mark_ready_404_for_bad_pk(self):
        response = self.client.post(reverse('mark_ready', args=[9999]))
        self.assertEqual(response.status_code, 404)


class DetailViewShowsDiffTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.lead = JobLead.objects.create(
            company='Gamma Corp',
            role='Technical Analyst',
            job_description='TA role.',
            source='adzuna',
            source_url='https://example.com/jobs/diff-test',
            cv_original_text='Original summary line\nSkills: Python',
            cv_tailored_text='Tailored summary line\nSkills: Python, Django',
        )

    def test_detail_passes_diff_to_context_when_cv_tailored(self):
        response = self.client.get(reverse('job_lead_detail', args=[self.lead.pk]))
        self.assertIsNotNone(response.context['diff'])

    def test_detail_diff_is_none_when_no_cv_text(self):
        lead = JobLead.objects.create(
            company='No CV Co', role='Junior Dev',
            job_description='JD.', source='manual',
            source_url='https://example.com/jobs/no-cv',
        )
        response = self.client.get(reverse('job_lead_detail', args=[lead.pk]))
        self.assertIsNone(response.context['diff'])

    def test_detail_shows_tailor_button_when_not_tailored(self):
        lead = JobLead.objects.create(
            company='No Tailor Co', role='Junior Dev',
            job_description='JD.', source='manual',
            source_url='https://example.com/jobs/no-tailor',
        )
        response = self.client.get(reverse('job_lead_detail', args=[lead.pk]))
        self.assertContains(response, 'Tailor CV with Claude')

    def test_detail_shows_approve_button_when_tailored(self):
        response = self.client.get(reverse('job_lead_detail', args=[self.lead.pk]))
        self.assertContains(response, 'Approve')


# ---------------------------------------------------------------------------
# Phase 4 — URL scraping + apply flow
# ---------------------------------------------------------------------------

class JobScraperTest(TestCase):

    def _make_html(self, body_text):
        return f'<html><body><div class="job-description">{body_text}</div></body></html>'

    @patch('tracker.services.job_scraper.httpx.get')
    @patch('tracker.services.job_scraper.anthropic.Anthropic')
    def test_scrape_returns_expected_fields(self, mock_anthropic_cls, mock_get):
        mock_get.return_value.text = self._make_html('A' * 300)
        mock_get.return_value.raise_for_status = lambda: None

        mock_message = MagicMock()
        mock_message.content[0].text = '{"company":"Acme","role":"Junior Dev","location":"Dublin","salary_range":"€30,000","job_description":"Build things"}'
        mock_anthropic_cls.return_value.messages.create.return_value = mock_message

        from tracker.services.job_scraper import scrape_job_url
        result = scrape_job_url('https://example.com/job/1')

        self.assertEqual(result['company'], 'Acme')
        self.assertEqual(result['role'], 'Junior Dev')
        self.assertEqual(result['location'], 'Dublin')
        self.assertIn('job_description', result)

    @patch('tracker.services.job_scraper.httpx.get')
    def test_scrape_raises_on_short_content(self, mock_get):
        mock_get.return_value.text = '<html><body>Login</body></html>'
        mock_get.return_value.raise_for_status = lambda: None

        from tracker.services.job_scraper import scrape_job_url
        with self.assertRaises(ValueError):
            scrape_job_url('https://example.com/job/login-wall')

    @patch('tracker.services.job_scraper.httpx.get')
    @patch('tracker.services.job_scraper.anthropic.Anthropic')
    def test_scrape_strips_markdown_fences(self, mock_anthropic_cls, mock_get):
        mock_get.return_value.text = self._make_html('B' * 300)
        mock_get.return_value.raise_for_status = lambda: None

        mock_message = MagicMock()
        mock_message.content[0].text = '```json\n{"company":"X","role":"Y","location":"","salary_range":"","job_description":"desc"}\n```'
        mock_anthropic_cls.return_value.messages.create.return_value = mock_message

        from tracker.services.job_scraper import scrape_job_url
        result = scrape_job_url('https://example.com/job/2')
        self.assertEqual(result['company'], 'X')


class AddFromURLViewTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_get_renders_url_form(self):
        response = self.client.get(reverse('add_from_url'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paste a job posting URL')

    @patch('tracker.services.job_scraper.httpx.get')
    @patch('tracker.services.job_scraper.anthropic.Anthropic')
    def test_url_submit_shows_confirm_form(self, mock_anthropic_cls, mock_get):
        mock_get.return_value.text = '<html><body><div class="job-description">' + 'X' * 400 + '</div></body></html>'
        mock_get.return_value.raise_for_status = lambda: None

        mock_message = MagicMock()
        mock_message.content[0].text = '{"company":"TestCo","role":"Analyst","location":"Dublin","salary_range":"","job_description":"Do analysis"}'
        mock_anthropic_cls.return_value.messages.create.return_value = mock_message

        response = self.client.post(reverse('add_from_url'), {
            'url': 'https://example.com/job/3',
            'url_submit': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TestCo')
        self.assertContains(response, 'Review')

    def test_confirm_submit_creates_lead(self):
        response = self.client.post(reverse('add_from_url'), {
            'company': 'FirmX',
            'role': 'Graduate Dev',
            'location': 'Remote',
            'salary_range': '€28,000',
            'source_url': 'https://example.com/job/4',
            'job_description': 'Build awesome things.',
            'confirm_submit': '1',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JobLead.objects.filter(company='FirmX').exists())
        lead = JobLead.objects.get(company='FirmX')
        self.assertEqual(lead.source, 'manual')
        self.assertEqual(lead.status, 'new')

    def test_confirm_submit_redirects_to_detail(self):
        response = self.client.post(reverse('add_from_url'), {
            'company': 'FirmY',
            'role': 'Junior BA',
            'location': 'Dublin',
            'salary_range': '',
            'source_url': 'https://example.com/job/5',
            'job_description': 'Analyse things.',
            'confirm_submit': '1',
        })
        lead = JobLead.objects.get(company='FirmY')
        self.assertRedirects(response, reverse('job_lead_detail', args=[lead.pk]))


class ApplyLeadViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.lead = JobLead.objects.create(
            company='ApplyCo',
            role='Junior Dev',
            location='Dublin',
            job_description='Write code.',
            source='manual',
            source_url='https://example.com/apply/1',
            status='ready',
            cv_path='/CVs/Applications/ApplyCo_JuniorDev_2026-05-25.docx',
        )

    def test_apply_creates_application(self):
        self.client.post(reverse('apply_lead', args=[self.lead.pk]))
        self.assertTrue(Application.objects.filter(company='ApplyCo').exists())

    def test_apply_sets_lead_status_applied(self):
        self.client.post(reverse('apply_lead', args=[self.lead.pk]))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, 'applied')

    def test_apply_links_lead_to_application(self):
        self.client.post(reverse('apply_lead', args=[self.lead.pk]))
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.application)

    def test_apply_renders_redirect_template(self):
        response = self.client.post(reverse('apply_lead', args=[self.lead.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Application recorded')

    def test_apply_get_redirects_to_detail(self):
        response = self.client.get(reverse('apply_lead', args=[self.lead.pk]))
        self.assertRedirects(response, reverse('job_lead_detail', args=[self.lead.pk]))

    def test_apply_button_visible_on_ready_lead(self):
        response = self.client.get(reverse('job_lead_detail', args=[self.lead.pk]))
        self.assertContains(response, 'Apply')

    def test_apply_button_not_visible_on_new_lead(self):
        self.lead.status = 'new'
        self.lead.save()
        response = self.client.get(reverse('job_lead_detail', args=[self.lead.pk]))
        self.assertNotContains(response, 'Apply — Record')


class Phase4URLTest(TestCase):

    def test_add_from_url_resolves(self):
        from django.urls import resolve
        self.assertEqual(resolve('/queue/add/').view_name, 'add_from_url')

    def test_apply_lead_resolves(self):
        from django.urls import resolve
        self.assertEqual(resolve('/queue/1/apply/').view_name, 'apply_lead')


# ---------------------------------------------------------------------------
# Phase 5 — Email digest
# ---------------------------------------------------------------------------

class SendDigestCommandTest(TestCase):

    def _make_lead(self, company, hours_ago=1):
        from django.utils import timezone
        lead = JobLead.objects.create(
            company=company,
            role='Junior Dev',
            job_description='JD',
            source='adzuna',
            source_url=f'https://example.com/jobs/{company.lower()}',
            status='new',
        )
        # auto_now_add prevents setting date_found in create(); force it via update
        JobLead.objects.filter(pk=lead.pk).update(
            date_found=timezone.now() - datetime.timedelta(hours=hours_ago)
        )
        lead.refresh_from_db()
        return lead

    @patch('tracker.management.commands.send_digest.send_mail')
    def test_digest_sends_to_recipient(self, mock_send):
        self._make_lead('Acme')
        with self.settings(DIGEST_RECIPIENT='test@example.com', DEFAULT_FROM_EMAIL='from@example.com'):
            from django.core.management import call_command
            call_command('send_digest', '--app-url=http://localhost/')
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        self.assertIn('test@example.com', kwargs.get('recipient_list', args[3] if len(args) > 3 else []))

    @patch('tracker.management.commands.send_digest.send_mail')
    def test_digest_skips_when_no_new_leads(self, mock_send):
        with self.settings(DIGEST_RECIPIENT='test@example.com'):
            from django.core.management import call_command
            call_command('send_digest')
        mock_send.assert_not_called()

    @patch('tracker.management.commands.send_digest.send_mail')
    def test_digest_force_sends_even_with_no_leads(self, mock_send):
        with self.settings(DIGEST_RECIPIENT='test@example.com', DEFAULT_FROM_EMAIL='from@example.com'):
            from django.core.management import call_command
            call_command('send_digest', '--force', '--app-url=http://localhost/')
        mock_send.assert_called_once()

    @patch('tracker.management.commands.send_digest.send_mail')
    def test_digest_subject_includes_count(self, mock_send):
        self._make_lead('FirmA')
        self._make_lead('FirmB')
        with self.settings(DIGEST_RECIPIENT='test@example.com', DEFAULT_FROM_EMAIL='from@example.com'):
            from django.core.management import call_command
            call_command('send_digest', '--app-url=http://localhost/')
        _, kwargs = mock_send.call_args
        self.assertIn('2', kwargs['subject'])

    @patch('tracker.management.commands.send_digest.send_mail')
    def test_digest_excludes_old_leads(self, mock_send):
        self._make_lead('OldFirm', hours_ago=26)  # older than 24 h
        with self.settings(DIGEST_RECIPIENT='test@example.com'):
            from django.core.management import call_command
            call_command('send_digest')
        mock_send.assert_not_called()

    @patch('tracker.management.commands.send_digest.send_mail')
    def test_digest_aborts_when_no_recipient_set(self, mock_send):
        self._make_lead('Firm')
        with self.settings(DIGEST_RECIPIENT=''):
            from django.core.management import call_command
            call_command('send_digest')
        mock_send.assert_not_called()

    @patch('tracker.management.commands.send_digest.send_mail')
    def test_digest_html_contains_lead_company(self, mock_send):
        self._make_lead('HtmlCo')
        with self.settings(DIGEST_RECIPIENT='test@example.com', DEFAULT_FROM_EMAIL='from@example.com'):
            from django.core.management import call_command
            call_command('send_digest', '--app-url=http://localhost/')
        args, kwargs = mock_send.call_args
        html = kwargs.get('html_message', '')
        self.assertIn('HtmlCo', html)


# ---------------------------------------------------------------------------
# Phase 6 — Gmail sync
# ---------------------------------------------------------------------------

class GmailClassifyTest(TestCase):
    """Unit tests for the _classify helper — no network calls needed."""

    def _classify(self, subject, body=''):
        from tracker.management.commands.sync_gmail import _classify
        return _classify(subject, body)

    def test_rejection_subject(self):
        self.assertEqual(self._classify('Unfortunately, your application was unsuccessful'), 'rejected')

    def test_interview_subject(self):
        self.assertEqual(self._classify('We would like to invite you to an interview'), 'interview_scheduled')

    def test_offer_subject(self):
        self.assertEqual(self._classify("We're pleased to offer you the position"), 'offer')

    def test_offer_beats_interview_in_same_text(self):
        # offer pattern takes priority over interview pattern
        self.assertEqual(self._classify('Job offer — interview feedback'), 'offer')

    def test_no_match_returns_none(self):
        self.assertIsNone(self._classify('Your application has been received'))

    def test_rejection_in_body(self):
        self.assertEqual(self._classify('Update on your application', 'We regret to inform you that you have not been selected.'), 'rejected')

    def test_interview_in_body(self):
        self.assertEqual(self._classify('Next steps', 'We would like to schedule a call to discuss the next step.'), 'interview_scheduled')

    def test_case_insensitive(self):
        self.assertEqual(self._classify('UNFORTUNATELY WE WILL NOT BE MOVING FORWARD'), 'rejected')


class SyncGmailCommandTest(TestCase):

    def setUp(self):
        self.app = Application.objects.create(
            company='Acme Corp',
            role='Junior Developer',
            date_applied=datetime.date.today(),
            status='applied',
        )

    def _make_raw_message(self, subject: str, sender: str = 'hr@acme.com', body: str = '') -> bytes:
        """Build a minimal RFC822 message bytes object."""
        import email.mime.text
        msg = email.mime.text.MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = 'joshua@example.com'
        return msg.as_bytes()

    def _mock_imap(self, messages: list[tuple[str, str, str]]):
        """Return a mock IMAP4_SSL that yields the given (subject, sender, body) messages."""
        raw_msgs = [self._make_raw_message(s, f, b) for s, f, b in messages]
        # imaplib.fetch returns a list of (header_bytes, message_bytes) tuples
        fetch_data = [(b'1 (RFC822 {100}', raw) for raw in raw_msgs]

        mock_imap = MagicMock()
        mock_imap.__enter__ = lambda s: s
        mock_imap.__exit__ = MagicMock(return_value=False)
        mock_imap.search.return_value = (None, [b' '.join(str(i).encode() for i in range(1, len(messages) + 1))])
        mock_imap.fetch.return_value = (None, fetch_data)
        mock_imap.select.return_value = (None, [b'1'])
        return mock_imap

    @patch('tracker.management.commands.sync_gmail.imaplib.IMAP4_SSL')
    def test_rejection_email_updates_status(self, mock_ssl):
        mock_ssl.return_value = self._mock_imap([
            ('Unfortunately your application was unsuccessful', 'hr@acme.com', ''),
        ])
        with self.settings(EMAIL_HOST_USER='u@g.com', EMAIL_HOST_PASSWORD='pw'):
            from django.core.management import call_command
            call_command('sync_gmail')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'rejected')

    @patch('tracker.management.commands.sync_gmail.imaplib.IMAP4_SSL')
    def test_interview_email_updates_status(self, mock_ssl):
        mock_ssl.return_value = self._mock_imap([
            ('Acme Corp — we would like to invite you to an interview', 'hr@acme.com', ''),
        ])
        with self.settings(EMAIL_HOST_USER='u@g.com', EMAIL_HOST_PASSWORD='pw'):
            from django.core.management import call_command
            call_command('sync_gmail')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'interview_scheduled')

    @patch('tracker.management.commands.sync_gmail.imaplib.IMAP4_SSL')
    def test_offer_email_updates_status(self, mock_ssl):
        mock_ssl.return_value = self._mock_imap([
            ('Acme Corp — pleased to offer you the role', 'hr@acme.com', ''),
        ])
        with self.settings(EMAIL_HOST_USER='u@g.com', EMAIL_HOST_PASSWORD='pw'):
            from django.core.management import call_command
            call_command('sync_gmail')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'offer')

    @patch('tracker.management.commands.sync_gmail.imaplib.IMAP4_SSL')
    def test_unrelated_email_does_not_update_status(self, mock_ssl):
        mock_ssl.return_value = self._mock_imap([
            ('Your Amazon order has been dispatched', 'noreply@amazon.com', ''),
        ])
        with self.settings(EMAIL_HOST_USER='u@g.com', EMAIL_HOST_PASSWORD='pw'):
            from django.core.management import call_command
            call_command('sync_gmail')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'applied')

    @patch('tracker.management.commands.sync_gmail.imaplib.IMAP4_SSL')
    def test_does_not_downgrade_status(self, mock_ssl):
        self.app.status = 'interview_scheduled'
        self.app.save()
        # a "thank you for applying" type email shouldn't move status back
        mock_ssl.return_value = self._mock_imap([
            ('Acme — interview scheduled confirmation', 'hr@acme.com', ''),
        ])
        with self.settings(EMAIL_HOST_USER='u@g.com', EMAIL_HOST_PASSWORD='pw'):
            from django.core.management import call_command
            call_command('sync_gmail')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'interview_scheduled')

    @patch('tracker.management.commands.sync_gmail.imaplib.IMAP4_SSL')
    def test_terminal_status_not_changed(self, mock_ssl):
        self.app.status = 'offer'
        self.app.save()
        mock_ssl.return_value = self._mock_imap([
            ('Unfortunately Acme Corp has decided not to proceed', 'hr@acme.com', ''),
        ])
        with self.settings(EMAIL_HOST_USER='u@g.com', EMAIL_HOST_PASSWORD='pw'):
            from django.core.management import call_command
            call_command('sync_gmail')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'offer')

    @patch('tracker.management.commands.sync_gmail.imaplib.IMAP4_SSL')
    def test_dry_run_does_not_save(self, mock_ssl):
        mock_ssl.return_value = self._mock_imap([
            ('Unfortunately Acme Corp application unsuccessful', 'hr@acme.com', ''),
        ])
        with self.settings(EMAIL_HOST_USER='u@g.com', EMAIL_HOST_PASSWORD='pw'):
            from django.core.management import call_command
            call_command('sync_gmail', '--dry-run')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'applied')

    def test_aborts_when_credentials_missing(self):
        with self.settings(EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD=''):
            from io import StringIO
            from django.core.management import call_command
            err = StringIO()
            call_command('sync_gmail', stderr=err)
        self.assertIn('must be set', err.getvalue())


# ---------------------------------------------------------------------------
# Clean job description utility
# ---------------------------------------------------------------------------

class CleanJobDescriptionTest(TestCase):

    def _clean(self, text):
        from tracker.services.utils import clean_job_description
        return clean_job_description(text)

    def test_decodes_html_entities(self):
        self.assertEqual(self._clean('Don&#8217;t miss this&#160;role'), "Don't miss this role")

    def test_decodes_amp_entity(self):
        self.assertEqual(self._clean('Sales &amp; Marketing'), 'Sales & Marketing')

    def test_strips_residual_html_tags(self):
        self.assertNotIn('<p>', self._clean('<p>Hello world</p>'))

    def test_removes_markdown_bold(self):
        self.assertEqual(self._clean('**Requirements**'), 'Requirements')

    def test_removes_markdown_italic(self):
        self.assertEqual(self._clean('*experience required*'), 'experience required')

    def test_removes_markdown_headers(self):
        self.assertEqual(self._clean('## About the role'), 'About the role')

    def test_collapses_excess_newlines(self):
        result = self._clean('Line one\n\n\n\n\nLine two')
        self.assertNotIn('\n\n\n', result)

    def test_collapses_multiple_spaces(self):
        self.assertNotIn('  ', self._clean('Too   many   spaces'))

    def test_strips_each_line(self):
        result = self._clean('  indented line  \n  another  ')
        for line in result.splitlines():
            self.assertEqual(line, line.strip())

    def test_converts_smart_quotes(self):
        self.assertNotIn('’', self._clean('It’s a great role'))

    def test_empty_string_returns_empty(self):
        self.assertEqual(self._clean(''), '')

    def test_none_returns_none(self):
        self.assertIsNone(self._clean(None))
