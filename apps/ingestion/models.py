"""
Models for data ingestion from CSV, API, and other sources.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class DataSource(models.Model):
    """
    External data sources for job imports.
    Admins can configure API endpoints or CSV URLs.
    """
    
    class SourceType(models.TextChoices):
        CSV_URL = 'CSV_URL', 'CSV File URL'
        API_JSON = 'API_JSON', 'JSON API Endpoint'
        API_XML = 'API_XML', 'XML API Endpoint'
        GOOGLE_SHEETS = 'GOOGLE_SHEETS', 'Google Sheets'
    
    name = models.CharField(max_length=200)
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    url = models.URLField(help_text="API endpoint or CSV file URL")
    
    # Authentication (for APIs)
    api_key = models.CharField(max_length=500, blank=True)
    api_secret = models.CharField(max_length=500, blank=True)
    auth_type = models.CharField(
        max_length=20,
        choices=[('NONE', 'None'), ('BEARER', 'Bearer Token'), ('BASIC', 'Basic Auth')],
        default='NONE'
    )
    
    # Scheduling
    is_active = models.BooleanField(default=True)
    sync_frequency = models.CharField(
        max_length=20,
        choices=[
            ('HOURLY', 'Every Hour'),
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MANUAL', 'Manual Only'),
        ],
        default='DAILY'
    )
    
    last_sync = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(
        max_length=20,
        choices=[
            ('SUCCESS', 'Success'),
            ('FAILED', 'Failed'),
            ('RUNNING', 'Running'),
        ],
        null=True,
        blank=True
    )
    
    # Trust settings
    default_trust_score = models.IntegerField(default=90)
    auto_approve = models.BooleanField(default=True)
    
    # Field mapping (JSON)
    field_mapping = models.JSONField(
        default=dict,
        help_text="Map source fields to JobVacancy fields"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='data_sources'
    )
    
    class Meta:
        db_table = 'data_sources'
        verbose_name = 'Data Source'
        verbose_name_plural = 'Data Sources'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"


class IngestionJob(models.Model):
    """
    Track individual ingestion jobs/attempts.
    """
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        PARTIAL = 'PARTIAL', 'Partially Completed'
    
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='ingestion_jobs',
        null=True,
        blank=True
    )
    
    # For manual file uploads
    uploaded_file = models.FileField(
        upload_to='ingestion/csv/%Y/%m/',
        null=True,
        blank=True
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    created_records = models.IntegerField(default=0)
    updated_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    
    error_log = models.TextField(blank=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ingestion_jobs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ingestion_jobs'
        ordering = ['-created_at']
    
    def __str__(self):
        if self.data_source:
            return f"Ingestion from {self.data_source.name} at {self.created_at}"
        return f"Manual Upload at {self.created_at}"
    
    def mark_completed(self):
        """Mark job as completed."""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
    
    def mark_failed(self, error_message):
        """Mark job as failed with error."""
        self.status = self.Status.FAILED
        self.completed_at = timezone.now()
        self.error_log = error_message
        self.save(update_fields=['status', 'completed_at', 'error_log'])