"""
Job vacancy models with trust scoring and verification system.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class JobCategory(models.Model):
    """
    Job categories for better organization and filtering.
    Examples: Technology, Healthcare, Education, Finance
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Font Awesome icon class (e.g., 'fa-code')"
    )
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'job_categories'
        verbose_name = 'Job Category'
        verbose_name_plural = 'Job Categories'
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_job_count(self):
        """Return number of active jobs in this category."""
        return self.jobs.filter(
            is_approved=True,
            expiry_date__gte=timezone.now().date()
        ).count()


class JobVacancy(models.Model):
    """
    Unified job vacancy model for all sources.
    Normalizes data from CSV, API, Employer posts, and User submissions.
    """
    
    # Source Type Enumeration
    class SourceType(models.TextChoices):
        ADMIN_CSV = 'ADMIN_CSV', 'Admin CSV Upload'
        ADMIN_API = 'ADMIN_API', 'Admin API Fetch'
        VERIFIED_EMPLOYER = 'EMP_VERIFIED', 'Verified Employer'
        GENERAL_USER = 'USER_GEN', 'General User'
    
    # Job Type Enumeration
    class JobType(models.TextChoices):
        FULL_TIME = 'FT', 'Full Time'
        PART_TIME = 'PT', 'Part Time'
        CONTRACT = 'CT', 'Contract'
        INTERNSHIP = 'IN', 'Internship'
        REMOTE = 'RM', 'Remote'
        HYBRID = 'HY', 'Hybrid'
        FREELANCE = 'FL', 'Freelance'
    
    # Experience Level Enumeration
    class ExperienceLevel(models.TextChoices):
        ENTRY = 'ENTRY', 'Entry Level (0-2 years)'
        JUNIOR = 'JUNIOR', 'Junior (2-4 years)'
        MID = 'MID', 'Mid Level (4-7 years)'
        SENIOR = 'SENIOR', 'Senior (7-10 years)'
        LEAD = 'LEAD', 'Lead/Manager (10+ years)'
    
    # Location Type
    class LocationType(models.TextChoices):
        MALAWI_CITY = 'MW_CITY', 'Malawi City'
        MALAWI_DISTRICT = 'MW_DIST', 'Malawi District'
        INTERNATIONAL = 'INTL', 'International'
        REMOTE = 'REMOTE', 'Remote'
    
    # ============================================
    # CORE JOB INFORMATION
    # ============================================
    title = models.CharField(max_length=255, db_index=True)
    company_name = models.CharField(max_length=255, db_index=True)
    company_logo = models.URLField(blank=True, null=True)
    company_website = models.URLField(blank=True, null=True)
    
    # Category relationship
    category = models.ForeignKey(
        JobCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs'
    )
    
    # Description and Requirements
    description = models.TextField()
    requirements = models.TextField(blank=True, help_text="Detailed requirements")
    responsibilities = models.TextField(blank=True)
    
    # Structured Data for AI Matching (CRITICAL)
    required_skills = models.TextField(
        help_text="Comma-separated skills: Python, Django, Project Management"
    )
    
    required_qualifications = models.TextField(
        blank=True,
        help_text="Required degrees, certifications"
    )
    
    experience_level = models.CharField(
        max_length=20,
        choices=ExperienceLevel.choices,
        default=ExperienceLevel.ENTRY
    )
    
    years_of_experience_required = models.PositiveIntegerField(
        default=0,
        help_text="Minimum years of experience required"
    )
    
    # ============================================
    # LOCATION INFORMATION
    # ============================================
    location_type = models.CharField(
        max_length=20,
        choices=LocationType.choices,
        default=LocationType.MALAWI_CITY
    )
    
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Malawi')
    
    # For display purposes
    location_display = models.CharField(
        max_length=255,
        blank=True,
        help_text="Formatted location for display (e.g., 'Lilongwe, Malawi')"
    )
    
    is_remote = models.BooleanField(default=False)
    
    # ============================================
    # JOB DETAILS
    # ============================================
    job_type = models.CharField(
        max_length=2,
        choices=JobType.choices,
        default=JobType.FULL_TIME
    )
    
    salary_min = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    salary_max = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    salary_currency = models.CharField(max_length=3, default='MWK')
    salary_is_displayed = models.BooleanField(default=False)
    
    # Application Details
    application_url = models.URLField(
        blank=True,
        null=True,
        help_text="External application link"
    )
    
    application_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email for direct applications"
    )
    
    application_deadline = models.DateField(null=True, blank=True)
    
    # ============================================
    # TRUST & VERIFICATION SYSTEM
    # ============================================
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.GENERAL_USER
    )
    
    trust_score = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="0-100 score based on source and verification"
    )
    
    is_approved = models.BooleanField(
        default=False,
        help_text="Admin approval status"
    )
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_jobs'
    )
    
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Verification flags
    is_verified_company = models.BooleanField(default=False)
    has_suspicious_content = models.BooleanField(default=False)
    report_count = models.IntegerField(default=0)
    
    # ============================================
    # FRESHNESS & EXPIRY
    # ============================================
    date_posted = models.DateTimeField(auto_now_add=True, db_index=True)
    date_updated = models.DateTimeField(auto_now=True)
    expiry_date = models.DateField(db_index=True)
    
    # Source tracking
    external_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID from external system/API"
    )
    
    source_url = models.URLField(
        blank=True,
        help_text="Original source URL if scraped/imported"
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posted_jobs'
    )
    
    # ============================================
    # STATISTICS
    # ============================================
    view_count = models.IntegerField(default=0)
    application_count = models.IntegerField(default=0)
    save_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'job_vacancies'
        verbose_name = 'Job Vacancy'
        verbose_name_plural = 'Job Vacancies'
        ordering = ['-date_posted']
        indexes = [
            models.Index(fields=['expiry_date', 'is_approved']),
            models.Index(fields=['location_type', 'city']),
            models.Index(fields=['job_type', 'experience_level']),
            models.Index(fields=['trust_score']),
            models.Index(fields=['date_posted', 'is_approved']),
        ]
    
    def __str__(self):
        return f"{self.title} at {self.company_name}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate fields before saving."""
        # Set location display
        if not self.location_display:
            parts = []
            if self.city:
                parts.append(self.city)
            if self.district:
                parts.append(self.district)
            if self.country:
                parts.append(self.country)
            self.location_display = ', '.join(parts) if parts else 'Location Not Specified'
        
        # Calculate trust score based on source
        if not self.pk:  # Only on creation
            trust_scores = {
                self.SourceType.ADMIN_CSV: 95,
                self.SourceType.ADMIN_API: 90,
                self.SourceType.VERIFIED_EMPLOYER: 85,
                self.SourceType.GENERAL_USER: 50,
            }
            self.trust_score = trust_scores.get(self.source_type, 50)
        
        super().save(*args, **kwargs)
    
    def is_expired(self):
        """Check if job has expired."""
        return self.expiry_date < timezone.now().date()
    
    def is_expiring_soon(self, days=7):
        """Check if job is expiring within the specified number of days."""
        if self.is_expired():
            return False
        days_until_expiry = (self.expiry_date - timezone.now().date()).days
        return 0 < days_until_expiry <= days
    
    def days_until_expiry(self):
        """Get the number of days until the job expires."""
        if self.is_expired():
            return 0
        return (self.expiry_date - timezone.now().date()).days
    
    def is_fresh(self):
        """Check if job is recent (posted within 7 days)."""
        days_since_posted = (timezone.now().date() - self.date_posted.date()).days
        return days_since_posted <= 7
    
    def get_skills_list(self):
        """Return skills as a clean list for AI matching."""
        if not self.required_skills:
            return []
        return [skill.strip().lower() for skill in self.required_skills.split(',') if skill.strip()]
    
    def get_match_score(self, user_skills_list):
        """Calculate simple skill match percentage."""
        if not user_skills_list:
            return 0
        
        job_skills = set(self.get_skills_list())
        user_skills = set(user_skills_list)
        
        if not job_skills:
            return 0
        
        matches = job_skills.intersection(user_skills)
        return int((len(matches) / len(job_skills)) * 100)
    
    def increment_view_count(self):
        """Increment view count atomically."""
        JobVacancy.objects.filter(pk=self.pk).update(view_count=models.F('view_count') + 1)
    
    def report(self, user):
        """Handle job reporting."""
        self.report_count += 1
        if self.report_count >= 5:
            self.has_suspicious_content = True
        self.save(update_fields=['report_count', 'has_suspicious_content'])
        
        # Create report record
        JobReport.objects.create(
            job=self,
            reported_by=user,
            report_count_at_time=self.report_count
        )


class JobReport(models.Model):
    """Track user reports of suspicious jobs."""
    
    class ReportReason(models.TextChoices):
        EXPIRED = 'EXPIRED', 'Job has expired'
        INCORRECT = 'INCORRECT', 'Incorrect information'
        SUSPICIOUS = 'SUSPICIOUS', 'Suspicious posting'
        SPAM = 'SPAM', 'Spam or fake job'
        OTHER = 'OTHER', 'Other reason'
    
    job = models.ForeignKey(
        JobVacancy,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='job_reports'
    )
    
    reason = models.CharField(
        max_length=20,
        choices=ReportReason.choices,
        default=ReportReason.SUSPICIOUS
    )
    
    details = models.TextField(blank=True)
    report_count_at_time = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_reports'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'job_reports'
        ordering = ['-created_at']
        unique_together = ['job', 'reported_by']  # One report per user per job
    
    def __str__(self):
        return f"Report on {self.job.title} - {self.reason}"


class JobView(models.Model):
    """Track job views for analytics and recommendations."""
    
    job = models.ForeignKey(
        JobVacancy,
        on_delete=models.CASCADE,
        related_name='views'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='job_views'
    )
    
    viewed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    
    class Meta:
        db_table = 'job_views'
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['user', 'viewed_at']),
            models.Index(fields=['job', 'viewed_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} viewed {self.job.title}"


class SavedJob(models.Model):
    """User's saved/bookmarked jobs."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_jobs'
    )
    
    job = models.ForeignKey(
        JobVacancy,
        on_delete=models.CASCADE,
        related_name='saved_by'
    )
    
    saved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="Personal notes about this job")
    
    class Meta:
        db_table = 'saved_jobs'
        ordering = ['-saved_at']
        unique_together = ['user', 'job']  # Can't save same job twice
    
    def __str__(self):
        return f"{self.user.email} saved {self.job.title}"