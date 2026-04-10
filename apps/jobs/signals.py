"""
Signal handlers for job-related events.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import JobVacancy
from apps.notifications.services import NotificationSignalHandler


@receiver(post_save, sender=JobVacancy)
def on_job_saved(sender, instance, created, **kwargs):
    """
    Trigger notifications when a new job is approved.
    """
    if instance.is_approved:
        # Only trigger if it was just approved or newly created and auto-approved
        if created or kwargs.get('update_fields') and 'is_approved' in kwargs.get('update_fields', []):
            NotificationSignalHandler.on_job_created(instance)