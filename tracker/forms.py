from django import forms
from .models import Application, JobLead


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['company', 'role', 'date_applied', 'status', 'job_url', 'notes', 'contact', 'follow_up_date']
        widgets = {
            'date_applied': forms.DateInput(attrs={'type': 'date'}),
            'follow_up_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }


class URLPasteForm(forms.Form):
    url = forms.URLField(
        label='Job posting URL',
        max_length=2000,
        widget=forms.URLInput(attrs={
            'placeholder': 'https://ie.indeed.com/viewjob?jk=...',
            'class': 'w-full',
        }),
    )


class JobLeadConfirmForm(forms.ModelForm):
    """Pre-populated from scrape; user can correct before saving."""
    class Meta:
        model = JobLead
        fields = ['company', 'role', 'location', 'salary_range', 'job_description', 'source_url']
        widgets = {
            'job_description': forms.Textarea(attrs={'rows': 8}),
            'source_url': forms.URLInput(),
        }
