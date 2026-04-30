"""
Forms for notification preferences and job alerts.
"""
from django import forms
from .models import NotificationPreference, JobAlert


class NotificationPreferenceForm(forms.ModelForm):
    """
    Form for managing notification preferences.
    """
    
    class Meta:
        model = NotificationPreference
        fields = [
            'email_enabled', 'in_app_enabled', 'email_frequency',
            'match_threshold', 'notify_malawi_only',
            'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end'
        ]
        widgets = {
            'email_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'in_app_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_frequency': forms.Select(attrs={'class': 'form-select'}),
            'match_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 100
            }),
            'notify_malawi_only': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'quiet_hours_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'quiet_hours_start': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'quiet_hours_end': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['quiet_hours_start'].required = False
        self.fields['quiet_hours_end'].required = False


class JobAlertForm(forms.ModelForm):
    """Form for creating/editing job alerts."""
    
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., "Python Jobs in Lilongwe"'
        })
    )
    
    keywords = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Skills or job titles'
        })
    )
    
    location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'City or district'
        })
    )
    
    # Use proper job type choices matching the model
    JOB_TYPE_CHOICES = [
        ('FT', 'Full Time'),
        ('PT', 'Part Time'),
        ('CT', 'Contract'),
        ('IN', 'Internship'),
        ('RM', 'Remote'),
        ('HY', 'Hybrid'),
        ('FL', 'Freelance'),
    ]
    
    job_types = forms.MultipleChoiceField(
        choices=JOB_TYPE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    frequency = forms.ChoiceField(
        choices=[
            ('DAILY', 'Daily Digest'),
            ('WEEKLY', 'Weekly Summary'),
            ('INSTANT', 'Instant (When posted)'),
        ],
        initial='DAILY',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = JobAlert
        fields = ['name', 'keywords', 'location', 'frequency', 'job_types']
    
    def clean_job_types(self):
        """Ensure job_types is always a list."""
        value = self.cleaned_data.get('job_types', [])
        if value is None:
            return []
        return list(value)