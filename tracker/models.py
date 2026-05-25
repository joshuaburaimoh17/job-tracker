from django.db import models


class Application(models.Model):
    STATUS_CHOICES = [
        ('applied', 'Applied'),
        ('interview_scheduled', 'Interview Scheduled'),
        ('interview_done', 'Interview Done'),
        ('offer', 'Offer Received'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    company = models.CharField(max_length=200)
    role = models.CharField(max_length=200)
    date_applied = models.DateField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='applied')
    job_url = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    contact = models.CharField(max_length=200, blank=True, null=True)
    follow_up_date = models.DateField(blank=True, null=True)
    job_description = models.TextField(blank=True, null=True)
    cv_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.role} at {self.company}"

    class Meta:
        ordering = ['-date_applied']


class JobLead(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('ready', 'Ready to Apply'),
        ('applied', 'Applied'),
        ('dismissed', 'Dismissed'),
    ]

    SOURCE_CHOICES = [
        ('adzuna', 'Adzuna'),
        ('rss_indeed', 'Indeed RSS'),
        ('rss_remote', 'Remote RSS'),
        ('manual', 'Manual URL'),
    ]

    company = models.CharField(max_length=200)
    role = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    salary_range = models.CharField(max_length=100, blank=True)
    job_description = models.TextField()
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES, default='manual')
    source_url = models.URLField(unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    cv_original_text = models.TextField(blank=True)
    cv_tailored_text = models.TextField(blank=True)
    cv_path = models.CharField(max_length=500, blank=True)
    date_found = models.DateTimeField(auto_now_add=True)
    application = models.OneToOneField(
        'Application',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='job_lead',
    )

    def __str__(self):
        return f"{self.role} at {self.company}"

    class Meta:
        ordering = ['-date_found']
