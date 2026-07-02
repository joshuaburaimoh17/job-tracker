from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import ApplicationForm
from .models import Application, JobLead


class MarkAppliedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester', password='x')
        self.client.force_login(self.user)
        self.lead = JobLead.objects.create(
            company='Acme',
            role='Data Analyst',
            location='Dublin, Ireland',
            salary_range='€35k–€40k',
            job_description='Analyse data.',
            source_url='https://example.com/jobs/1',
            status=JobLead.STATUS_READY,
        )

    def test_mark_applied_creates_linked_application(self):
        response = self.client.post(reverse('tracker:mark_applied', args=[self.lead.pk]))

        self.lead.refresh_from_db()
        application = self.lead.application
        self.assertIsNotNone(application)
        self.assertRedirects(response, reverse('tracker:application_detail', args=[application.pk]))
        self.assertEqual(self.lead.status, JobLead.STATUS_APPLIED)
        self.assertEqual(application.company, 'Acme')
        self.assertEqual(application.role, 'Data Analyst')
        self.assertEqual(application.location, 'Dublin, Ireland')
        self.assertEqual(application.salary_range, '€35k–€40k')
        self.assertEqual(application.job_url, 'https://example.com/jobs/1')
        self.assertEqual(application.job_description, 'Analyse data.')
        self.assertEqual(application.status, Application.STATUS_APPLIED)
        self.assertEqual(application.date_applied, date.today())
        self.assertIsNotNone(application.status_updated_at)

    def test_mark_applied_twice_does_not_duplicate(self):
        self.client.post(reverse('tracker:mark_applied', args=[self.lead.pk]))
        self.client.post(reverse('tracker:mark_applied', args=[self.lead.pk]))
        self.assertEqual(Application.objects.count(), 1)


class StatusUpdatedAtTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester', password='x')
        self.client.force_login(self.user)
        self.application = Application.objects.create(
            company='Acme',
            role='Data Analyst',
            date_applied=date.today(),
            status=Application.STATUS_APPLIED,
        )

    def test_status_change_sets_timestamp(self):
        self.assertIsNone(self.application.status_updated_at)
        self.client.post(
            reverse('tracker:update_status', args=[self.application.pk]),
            {'status': Application.STATUS_IN_REVIEW},
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.STATUS_IN_REVIEW)
        self.assertIsNotNone(self.application.status_updated_at)

    def test_same_status_does_not_set_timestamp(self):
        self.client.post(
            reverse('tracker:update_status', args=[self.application.pk]),
            {'status': Application.STATUS_APPLIED},
        )
        self.application.refresh_from_db()
        self.assertIsNone(self.application.status_updated_at)


class UrlLengthTests(TestCase):
    def test_application_form_accepts_long_job_url(self):
        long_url = 'https://example.com/careers/' + 'a' * 400
        form = ApplicationForm(data={
            'company': 'Acme',
            'role': 'Data Analyst',
            'date_applied': date.today(),
            'status': Application.STATUS_APPLIED,
            'job_url': long_url,
        })
        self.assertTrue(form.is_valid(), form.errors)
