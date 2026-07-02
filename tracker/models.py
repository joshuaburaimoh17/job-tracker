from django.db import models


class Application(models.Model):
    STATUS_APPLIED = 'applied'
    STATUS_IN_REVIEW = 'in_review'
    STATUS_INTERVIEW_SCHEDULED = 'interview_scheduled'
    STATUS_INTERVIEW_DONE = 'interview_done'
    STATUS_OFFER = 'offer'
    STATUS_REJECTED = 'rejected'
    STATUS_WITHDRAWN = 'withdrawn'

    STATUS_CHOICES = [
        (STATUS_APPLIED, 'Applied'),
        (STATUS_IN_REVIEW, 'In Review'),
        (STATUS_INTERVIEW_SCHEDULED, 'Interview Scheduled'),
        (STATUS_INTERVIEW_DONE, 'Interview Done'),
        (STATUS_OFFER, 'Offer'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_WITHDRAWN, 'Withdrawn'),
    ]

    company = models.CharField(max_length=200)
    role = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    salary_range = models.CharField(max_length=100, blank=True)
    date_applied = models.DateField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_APPLIED)
    # Set only when status actually changes (not on every save) — powers
    # "no response in N days" follow-up logic, which updated_at cannot.
    status_updated_at = models.DateTimeField(blank=True, null=True)
    job_url = models.URLField(max_length=500, blank=True, null=True)
    job_description = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    contact_name = models.CharField(max_length=200, blank=True, null=True)
    follow_up_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_applied']

    def __str__(self):
        return f"{self.role} at {self.company}"


class JobLead(models.Model):
    STATUS_NEW = 'new'
    STATUS_READY = 'ready'
    STATUS_APPLIED = 'applied'
    STATUS_DISMISSED = 'dismissed'

    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_READY, 'Ready'),
        (STATUS_APPLIED, 'Applied'),
        (STATUS_DISMISSED, 'Dismissed'),
    ]

    company = models.CharField(max_length=200)
    role = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    salary_range = models.CharField(max_length=100, blank=True)
    job_description = models.TextField()
    source_url = models.URLField(max_length=500, unique=True, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    cv_original_text = models.TextField(blank=True)
    cv_tailored_text = models.TextField(blank=True)
    cv_changes = models.TextField(blank=True)
    cv_tailored_json = models.TextField(blank=True)
    date_found = models.DateTimeField(auto_now_add=True)
    application = models.OneToOneField(
        Application,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='job_lead',
    )

    class Meta:
        ordering = ['-date_found']

    def __str__(self):
        return f"{self.role} at {self.company}"
