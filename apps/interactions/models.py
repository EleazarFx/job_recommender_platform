"""
User interaction models for tracking applications and engagement.
"""
from django.db import models
from django.conf import settings


class JobApplication(models.Model):
    """
    Track job applications submitted through the platform.
    """
    
    class Status(models.TextChoices):
        APPLIED = 'APPLIED', 'Applied'
        REVIEWED = 'REVIEWED', 'Application Viewed'
        SHORTLISTED = 'SHORTLISTED', 'Shortlisted'
        INTERVIEW = 'INTERVIEW', 'Interview Scheduled'
        OFFER = 'OFFER', 'Offer Extended'
        REJECTED = 'REJECTED', 'Not Selected'
        WITHDRAWN = 'WITHDRAWN', 'Withdrawn'
    
    job = models.ForeignKey(
        'jobs.JobVacancy',
        on_delete=models.CASCADE,
        related_name='applications'
    )
    
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.APPLIED
    )
    
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Optional cover letter/notes
    cover_letter = models.TextField(blank=True)
    
    # Employer feedback
    employer_notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'job_applications'
        unique_together = ['job', 'applicant']
        ordering = ['-applied_at']
    
    def __str__(self):
        return f"{self.applicant.email} - {self.job.title}"