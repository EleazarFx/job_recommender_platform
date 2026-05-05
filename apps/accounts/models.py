
"""
Custom User Model and Authentication Models.
Email-based authentication with Profile extension.
"""
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.core.validators import MinLengthValidator
import random
import string


class UserManager(BaseUserManager):
    """Custom manager where email is the unique identifier."""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'ADMIN')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User Model - Email as unique identifier.
    Username field is kept for Django compatibility but not used.
    """
    # Remove username field entirely
    username = None
    
    # Email becomes the unique identifier
    email = models.EmailField(
        'Email Address',
        unique=True,
        error_messages={
            'unique': "A user with this email already exists.",
        }
    )
    
    # Additional fields for job platform
    USER_TYPE_CHOICES = (
        ('JOB_SEEKER', 'Job Seeker'),
        ('EMPLOYER', 'Employer'),
        ('ADMIN', 'Administrator'),
    )
    
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='JOB_SEEKER'
    )
    
    # Verification & Trust
    is_verified_employer = models.BooleanField(
        default=False,
        help_text="Admin verified employer account"
    )
    
    # Profile completion tracking
    profile_completion_percentage = models.IntegerField(default=0)
    
    # Timestamps
    date_joined = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    # Notification preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text="Receive email notifications about matching jobs"
    )
    in_app_notifications = models.BooleanField(
        default=True,
        help_text="Receive in-app notifications"
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']
    
    def __str__(self):
        return self.email
    
    @property
    def display_user_type(self):
        if self.is_superuser or self.is_staff:
            return 'Administrator'
        return self.get_user_type_display()
    
    @property
    def is_admin(self):
        """Treat any administrator account as admin, whether by role or staff status."""
        return self.is_superuser or self.is_staff or self.user_type == 'ADMIN'
    
    def get_full_name(self):
        """Return full name or email if name not set."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email
    
    def update_profile_completion(self):
        """Calculate and update profile completion percentage."""
        profile = self.profile
        if self.user_type == 'JOB_SEEKER':
            fields = ['skills', 'qualifications', 'experience_level', 
                      'preferred_locations', 'preferred_job_types']
            completed = sum(1 for field in fields if getattr(profile, field))
            self.profile_completion_percentage = int((completed / len(fields)) * 100)
        elif self.user_type == 'EMPLOYER':
            fields = [
                'company_name', 'company_website', 'company_description',
                'company_location', 'company_size', 'industry'
            ]
            completed = sum(1 for field in fields if getattr(profile, field))
            self.profile_completion_percentage = int((completed / len(fields)) * 100)
        else:
            # Admin profile does not require job seeker or employer fields.
            self.profile_completion_percentage = 100
        self.save(update_fields=['profile_completion_percentage'])

class Profile(models.Model):
    """
    Extended profile for both job seekers and employers.
    """
    EXPERIENCE_LEVELS = (
        ('ENTRY', 'Entry Level (0-2 years)'),
        ('JUNIOR', 'Junior (2-4 years)'),
        ('MID', 'Mid Level (4-7 years)'),
        ('SENIOR', 'Senior (7-10 years)'),
        ('LEAD', 'Lead/Manager (10+ years)'),
    )
    
    JOB_TYPES = (
        ('FULL_TIME', 'Full Time'),
        ('PART_TIME', 'Part Time'),
        ('CONTRACT', 'Contract'),
        ('INTERNSHIP', 'Internship'),
        ('REMOTE', 'Remote'),
        ('HYBRID', 'Hybrid'),
    )
    
    COMPANY_SIZE_CHOICES = (
        ('1-10', '1-10 employees'),
        ('11-50', '11-50 employees'),
        ('51-200', '51-200 employees'),
        ('201-500', '201-500 employees'),
        ('500+', '500+ employees'),
    )
    
    INDUSTRY_CHOICES = (
        ('TECH', 'Technology'),
        ('HEALTH', 'Healthcare'),
        ('EDUCATION', 'Education'),
        ('FINANCE', 'Finance'),
        ('AGRICULTURE', 'Agriculture'),
        ('HOSPITALITY', 'Hospitality'),
        ('RETAIL', 'Retail'),
        ('MANUFACTURING', 'Manufacturing'),
        ('OTHER', 'Other'),
    )
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Profile Picture
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/',
        blank=True,
        null=True
    )
    
    # ============================================
    # JOB SEEKER FIELDS
    # ============================================
    skills = models.TextField(
        blank=True,
        help_text="Comma-separated skills: Python, Django, Project Management"
    )
    
    qualifications = models.TextField(
        blank=True,
        help_text="Degrees, certifications, courses"
    )
    
    experience_level = models.CharField(
        max_length=20,
        choices=EXPERIENCE_LEVELS,
        blank=True
    )
    
    years_of_experience = models.PositiveIntegerField(default=0)
    
    # Location Preferences
    preferred_locations = models.TextField(
        blank=True,
        help_text="Lilongwe, Blantyre, Remote, International"
    )
    
    # Job Type Preferences (Stored as JSON)
    preferred_job_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of preferred job types"
    )
    
    # Resume/CV (Temporary storage - deleted after processing)
    cv_file = models.FileField(
        upload_to='cvs/temp/%Y/%m/',
        blank=True,
        null=True
    )
    
    # Extracted data from CV (for AI matching)
    extracted_skills = models.JSONField(
        default=list,
        blank=True
    )
    
    # ============================================
    # EMPLOYER FIELDS (NEW)
    # ============================================
    company_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Your company name"
    )
    
    company_website = models.URLField(
        blank=True,
        help_text="https://www.example.com"
    )
    
    company_description = models.TextField(
        blank=True,
        help_text="Tell potential applicants about your company"
    )
    
    company_location = models.CharField(
        max_length=255,
        blank=True,
        help_text="e.g., Lilongwe, Malawi"
    )
    
    company_size = models.CharField(
        max_length=20,
        choices=COMPANY_SIZE_CHOICES,
        blank=True
    )
    
    industry = models.CharField(
        max_length=20,
        choices=INDUSTRY_CHOICES,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'
    
    def __str__(self):
        return f"{self.user.email}'s Profile"
    
    def get_skills_list(self):
        """Return skills as a clean list."""
        if not self.skills:
            return []
        return [skill.strip() for skill in self.skills.split(',') if skill.strip()]
    
    def get_preferred_locations_list(self):
        """Return locations as a clean list."""
        if not self.preferred_locations:
            return []
        return [loc.strip() for loc in self.preferred_locations.split(',') if loc.strip()]

        
class PasswordResetOTP(models.Model):
    """
    One-Time Password for password reset.
    Expires after 10 minutes. One-time use only.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reset_otps'
    )
    
    code = models.CharField(
        max_length=6,
        validators=[MinLengthValidator(6)]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    
    # Track attempts to prevent brute force
    attempts = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'password_reset_otps'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP for {self.user.email} - {self.code}"
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_otp()
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        return super().save(*args, **kwargs)
    
    @staticmethod
    def generate_otp():
        """Generate secure 6-digit OTP."""
        return ''.join(random.choices(string.digits, k=6))
    
    def is_valid(self):
        """Check if OTP is still valid."""
        return (
            not self.is_used and
            self.expires_at > timezone.now() and
            self.attempts < 3
        )
    
    def mark_used(self):
        """Mark OTP as used after successful verification."""
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])


class LoginAttempt(models.Model):
    """
    Track failed login attempts for rate limiting.
    """
    email = models.EmailField()
    ip_address = models.GenericIPAddressField()
    attempt_time = models.DateTimeField(auto_now_add=True)
    is_successful = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'login_attempts'
        indexes = [
            models.Index(fields=['email', 'ip_address']),
            models.Index(fields=['attempt_time']),
        ]
    
    @classmethod
    def is_rate_limited(cls, email, ip_address):
        """Check if too many failed attempts in last 15 minutes."""
        cutoff = timezone.now() - timezone.timedelta(minutes=15)
        attempts = cls.objects.filter(
            email=email,
            ip_address=ip_address,
            is_successful=False,
            attempt_time__gte=cutoff
        ).count()
        return attempts >= 5  # Max 5 attempts in 15 minutes


class AdminAuditLog(models.Model):
    """
    Audit trail for administrative actions.
    """
    ACTION_TYPES = [
        ('ADMIN_CREATED', 'Administrator Account Created'),
        ('ADMIN_DELETED', 'Administrator Account Deleted'),
        ('PERMISSION_CHANGED', 'Permissions Changed'),
        ('SETTINGS_CHANGED', 'System Settings Changed'),
        ('DATA_EXPORT', 'Data Exported'),
    ]
    
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_actions'
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_actions_received'
    )
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'admin_audit_logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.action_type} by {self.performed_by} at {self.created_at}"