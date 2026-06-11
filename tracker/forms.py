from django import forms

from .models import Application, JobLead


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        exclude = ['created_at', 'updated_at']
        widgets = {
            'date_applied': forms.DateInput(attrs={'type': 'date'}),
            'follow_up_date': forms.DateInput(attrs={'type': 'date'}),
        }


class JobLeadForm(forms.ModelForm):
    class Meta:
        model = JobLead
        fields = ['role', 'company', 'location', 'salary_range', 'source_url', 'job_description']
        widgets = {
            'job_description': forms.Textarea(attrs={
                'rows': 14,
                'placeholder': 'Paste the full job description here',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ('location', 'salary_range', 'source_url'):
            self.fields[field].required = False

    def clean_source_url(self):
        # source_url is unique; store blank as NULL so multiple leads
        # without a URL don't collide on ''.
        return self.cleaned_data.get('source_url') or None
