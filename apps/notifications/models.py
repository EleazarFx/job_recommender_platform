"""
Notification models for email digests and in-app alerts.
Designed to prevent spam and respect user preferences.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class NotificationPreference(models.Model):
    """
    User's notification preferences.
    One-to-one with User model.
    """
    
    class Frequency(models.TextChoices):
        INSTANT = 'INSTANT', 'Instant (When posted)'
        DAILY = 'DAILY', 'Daily Digest'
        WEEKLY = 'WEEKLY', 'Weekly Summary'
        NEVER = 'NEVER', 'Never'
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Channel preferences
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    
    # Frequency settings
    email_frequency = models.CharField(
        max_length=10,
        choices=Frequency.choices,
        default=Frequency.DAILY
    )
    
    # Match threshold (only notify if match score >= this)
    match_threshold = models.IntegerField(
        default=60,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Location preferences for notifications
    notify_malawi_only = models.BooleanField(default=False)
    preferred_locations_filter = models.JSONField(default=list, blank=True)
    
    # Job type preferences
    notify_job_types = models.JSONField(default=list, blank=True)
    
    # Quiet hours (don't send emails during these times)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    
    # Timestamps
    last_notification_sent = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.email}"
    
    def should_send_email_now(self):
        """Check if email should be sent based on quiet hours."""
        if not self.quiet_hours_enabled:
            return True
        
        now = timezone.now().time()
        if self.quiet_hours_start and self.quiet_hours_end:
            if self.quiet_hours_start <= self.quiet_hours_end:
                return not (self.quiet_hours_start <= now <= self.quiet_hours_end)
            else:
                # Overnight quiet hours (e.g., 22:00 to 06:00)
                return not (now >= self.quiet_hours_start or now <= self.quiet_hours_end)
        
        return True


class JobAlert(models.Model):
    """
    Saved search alerts for users.
    Users receive notifications when new jobs match their criteria.
    """
    
    class Frequency(models.TextChoices):
        DAILY = 'DAILY', 'Daily'
        WEEKLY = 'WEEKLY', 'Weekly'
        INSTANT = 'INSTANT', 'Instant'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='job_alerts'
    )
    
    name = models.CharField(max_length=100)
    
    # Search criteria
    keywords = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    job_types = models.JSONField(default=list, blank=True)
    experience_level = models.CharField(max_length=20, blank=True)
    category = models.ForeignKey(
        'jobs.JobCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Alert settings
    frequency = models.CharField(
        max_length=10,
        choices=Frequency.choices,
        default=Frequency.DAILY
    )
    
    is_active = models.BooleanField(default=True)
    
    # Tracking
    last_triggered = models.DateTimeField(null=True, blank=True)
    jobs_found_last_trigger = models.IntegerField(default=0)
    total_jobs_found = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'job_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['frequency', 'last_triggered']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.user.email}"
    
    def get_matching_jobs(self, since=None):
        """Get jobs matching this alert's criteria."""
        from apps.jobs.models import JobVacancy
        from django.db.models import Q
        
        queryset = JobVacancy.objects.filter(
            is_approved=True,
            expiry_date__gte=timezone.now().date()
        )
        
        if since:
            queryset = queryset.filter(date_posted__gte=since)
        
        if self.keywords:
            queryset = queryset.filter(
                Q(title__icontains=self.keywords) |
                Q(description__icontains=self.keywords) |
                Q(required_skills__icontains=self.keywords)
            )
        
        if self.location:
            queryset = queryset.filter(location_display__icontains=self.location)
        
        if self.job_types:
            queryset = queryset.filter(job_type__in=self.job_types)
        
        if self.experience_level:
            queryset = queryset.filter(experience_level=self.experience_level)
        
        if self.category:
            queryset = queryset.filter(category=self.category)
        
        return queryset.distinct()


class Notification(models.Model):
    """
    Individual notification record.
    Can be in-app, email, or both.
    """
    
    class NotificationType(models.TextChoices):
        JOB_MATCH = 'JOB_MATCH', 'New Job Match'
        JOB_ALERT = 'JOB_ALERT', 'Job Alert'
        APPLICATION_UPDATE = 'APPLICATION_UPDATE', 'Application Update'
        JOB_EXPIRING = 'JOB_EXPIRING', 'Job Expiring Soon'
        SYSTEM = 'SYSTEM', 'System Notification'
    
    class DeliveryMethod(models.TextChoices):
        IN_APP = 'IN_APP', 'In-App Only'
        EMAIL = 'EMAIL', 'Email Only'
        BOTH = 'BOTH', 'Both'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Notification content
    type = models.CharField(max_length=20, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Related objects
    job = models.ForeignKey(
        'jobs.JobVacancy',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    job_alert = models.ForeignKey(
        JobAlert,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Delivery settings
    delivery_method = models.CharField(
        max_length=10,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.BOTH
    )
    
    # Status tracking
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    is_delivered = models.BooleanField(default=False)
    
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Match score (for job match notifications)
    match_score = models.FloatField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Scheduled for future delivery
    scheduled_for = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['type', 'created_at']),
            models.Index(fields=['scheduled_for']),
        ]
    
    def __str__(self):
        return f"{self.get_type_display()} for {self.user.email}"
    
    def mark_as_read(self):
        """Mark notification as read."""
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_sent(self):
        """Mark notification as sent."""
        self.is_sent = True
        self.sent_at = timezone.now()
        self.save(update_fields=['is_sent', 'sent_at'])


class NotificationDigest(models.Model):
    """
    Batched digest of multiple notifications.
    Used for daily/weekly email summaries.
    """
    
    class DigestType(models.TextChoices):
        DAILY = 'DAILY', 'Daily Digest'
        WEEKLY = 'WEEKLY', 'Weekly Digest'
        INSTANT = 'INSTANT', 'Instant Alert'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_digests'
    )
    
    digest_type = models.CharField(max_length=10, choices=DigestType.choices)
    
    # Content
    notifications = models.ManyToManyField(Notification)
    notification_count = models.IntegerField(default=0)
    
    # Summary stats
    new_jobs_count = models.IntegerField(default=0)
    job_matches_count = models.IntegerField(default=0)
    
    # Status
    is_sent = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    
    # Timestamps
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notification_digests'
        ordering = ['-period_end']
        unique_together = ['user', 'digest_type', 'period_start']
    
    def __str__(self):
        return f"{self.get_digest_type_display()} for {self.user.email} ({self.period_end.date()})"


class EmailLog(models.Model):
    """
    Log of all emails sent from the system.
    For debugging and compliance.
    """
    
    class EmailType(models.TextChoices):
        DIGEST = 'DIGEST', 'Digest Email'
        ALERT = 'ALERT', 'Job Alert'
        VERIFICATION = 'VERIFICATION', 'Email Verification'
        PASSWORD_RESET = 'PASSWORD_RESET', 'Password Reset'
        WELCOME = 'WELCOME', 'Welcome Email'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_logs'
    )
    
    email_type = models.CharField(max_length=20, choices=EmailType.choices)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    
    # Content tracking
    job_count = models.IntegerField(default=0)
    
    # Delivery status
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('SENT', 'Sent'),
            ('FAILED', 'Failed'),
            ('BOUNCED', 'Bounced'),
        ],
        default='PENDING'
    )
    
    error_message = models.TextField(blank=True)
    
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'email_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.get_email_type_display()} to {self.recipient} at {self.created_at}"