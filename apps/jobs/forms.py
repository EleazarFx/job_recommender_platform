"""
Search forms and filters for job discovery.
"""
from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
from .models import JobVacancy, JobCategory


class JobSearchForm(forms.Form):
    """
    Main job search form with all filter options.
    Designed for GET requests to enable bookmarkable URLs.
    """
    
    # Keyword search
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Job title, skills, or company...',
            'autocomplete': 'off'
        })
    )
    
    # Location filter
    location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'City, district, or "Remote"',
            'autocomplete': 'off'
        })
    )
    
    # Category filter
    category = forms.ModelChoiceField(
        queryset=JobCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Job Type filter
    job_type = forms.MultipleChoiceField(
        choices=JobVacancy.JobType.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    # Experience Level filter
    experience_level = forms.ChoiceField(
        choices=[('', 'Any Experience Level')] + list(JobVacancy.ExperienceLevel.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Date Posted filter
    date_posted = forms.ChoiceField(
        choices=[
            ('', 'Any Time'),
            ('1', 'Last 24 hours'),
            ('3', 'Last 3 days'),
            ('7', 'Last 7 days'),
            ('14', 'Last 14 days'),
            ('30', 'Last 30 days'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Salary filter (optional)
    salary_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min salary (MWK)'
        })
    )
    
    # Remote only
    remote_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # Verified employers only
    verified_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # Sort options
    sort_by = forms.ChoiceField(
        choices=[
            ('-date_posted', 'Most Recent'),
            ('date_posted', 'Oldest First'),
            ('-trust_score', 'Highest Trust Score'),
            ('company_name', 'Company Name (A-Z)'),
            ('title', 'Job Title (A-Z)'),
        ],
        required=False,
        initial='-date_posted',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean_date_posted(self):
        """Convert date posted choice to actual date."""
        days = self.cleaned_data.get('date_posted')
        if days:
            return timezone.now().date() - timedelta(days=int(days))
        return None
    
    def filter_queryset(self, queryset):
        """
        Apply all filters to the queryset.
        Returns filtered and annotated queryset.
        """
        from django.db.models import Q
        
        # Start with active, approved jobs
        queryset = queryset.filter(
            is_approved=True,
            expiry_date__gte=timezone.now().date()
        )
        
        # Keyword search
        q = self.cleaned_data.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(company_name__icontains=q) |
                Q(description__icontains=q) |
                Q(required_skills__icontains=q) |
                Q(location_display__icontains=q)
            ).distinct()
        
        # Location filter
        location = self.cleaned_data.get('location')
        if location:
            queryset = queryset.filter(
                Q(city__icontains=location) |
                Q(district__icontains=location) |
                Q(location_display__icontains=location)
            )
        
        # Category filter
        category = self.cleaned_data.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Job type filter
        job_types = self.cleaned_data.get('job_type')
        if job_types:
            queryset = queryset.filter(job_type__in=job_types)
        
        # Experience level filter
        experience_level = self.cleaned_data.get('experience_level')
        if experience_level:
            queryset = queryset.filter(experience_level=experience_level)
        
        # Date posted filter
        date_limit = self.cleaned_data.get('date_posted')
        if date_limit:
            queryset = queryset.filter(date_posted__date__gte=date_limit)
        
        # Salary filter
        salary_min = self.cleaned_data.get('salary_min')
        if salary_min:
            queryset = queryset.filter(
                Q(salary_min__gte=salary_min) | 
                Q(salary_max__gte=salary_min)
            )
        
        # Remote only
        if self.cleaned_data.get('remote_only'):
            queryset = queryset.filter(is_remote=True)
        
        # Verified employers only
        if self.cleaned_data.get('verified_only'):
            queryset = queryset.filter(is_verified_company=True)
        
        # Sorting
        sort_by = self.cleaned_data.get('sort_by', '-date_posted')
        queryset = queryset.order_by(sort_by)
        
        return queryset


class JobAlertForm(forms.Form):
    """
    Form for creating job alerts based on search criteria.
    """
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
    
    job_types = forms.MultipleChoiceField(
        choices=JobVacancy.JobType.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple()
    )
    
    frequency = forms.ChoiceField(
        choices=[
            ('daily', 'Daily Digest'),
            ('weekly', 'Weekly Summary'),
            ('instant', 'Instant (When posted)'),
        ],
        initial='daily',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class JobReportForm(forms.Form):
    """
    Form for reporting suspicious jobs.
    """
    reason = forms.ChoiceField(
        choices=[
            ('EXPIRED', 'Job has expired'),
            ('INCORRECT', 'Incorrect information'),
            ('SUSPICIOUS', 'Suspicious posting'),
            ('SPAM', 'Spam or fake job'),
            ('OTHER', 'Other reason'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    details = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Please provide additional details...'
        })
    )



class JobPostForm(forms.ModelForm):
    """
    Form for users to post new jobs.
    """
    
    class Meta:
        model = JobVacancy
        fields = [
            'title', 'company_name', 'category', 'location_display',
            'city', 'district', 'is_remote', 'job_type',
            'experience_level', 'years_of_experience_required',
            'required_skills', 'required_qualifications',
            'description', 'requirements', 'responsibilities',
            'salary_min', 'salary_max', 'salary_is_displayed',
            'application_url', 'application_email',
            'expiry_date'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'location_display': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., "Lilongwe, Malawi" or "Remote"'
            }),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'district': forms.TextInput(attrs={'class': 'form-control'}),
            'is_remote': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'job_type': forms.Select(attrs={'class': 'form-select'}),
            'experience_level': forms.Select(attrs={'class': 'form-select'}),
            'years_of_experience_required': forms.NumberInput(attrs={'class': 'form-control'}),
            'required_skills': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Python, Django, Project Management...'
            }),
            'required_qualifications': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Bachelor\'s degree in Computer Science...'
            }),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'responsibilities': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'salary_min': forms.NumberInput(attrs={'class': 'form-control'}),
            'salary_max': forms.NumberInput(attrs={'class': 'form-control'}),
            'salary_is_displayed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'application_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://...'
            }),
            'application_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'careers@company.com'
            }),
            'expiry_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'min': timezone.now().date().isoformat()
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure at least one application method is provided
        app_url = cleaned_data.get('application_url')
        app_email = cleaned_data.get('application_email')
        
        if not app_url and not app_email:
            raise forms.ValidationError(
                'Please provide either an application URL or email address.'
            )
        
        # Set default expiry if not provided
        if not cleaned_data.get('expiry_date'):
            cleaned_data['expiry_date'] = timezone.now().date() + timezone.timedelta(days=30)
        
        return cleaned_data