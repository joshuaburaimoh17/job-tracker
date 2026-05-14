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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.role} at {self.company}"

    class Meta:
        ordering = ['-date_applied']
