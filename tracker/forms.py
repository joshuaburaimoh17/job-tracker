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


class URLPasteForm(forms.Form):
    url = forms.URLField(
        label='Job Posting URL',
        widget=forms.URLInput(attrs={
            'placeholder': 'https://ie.indeed.com/viewjob?jk=...',
            'class': 'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm '
                     'text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none '
                     'focus:ring-1 focus:ring-indigo-500',
        }),
    )


class JobLeadConfirmForm(forms.ModelForm):
    class Meta:
        model = JobLead
        fields = ['role', 'company', 'location', 'salary_range', 'job_description', 'source_url']
        widgets = {
            'job_description': forms.Textarea(attrs={'rows': 14}),
        }
