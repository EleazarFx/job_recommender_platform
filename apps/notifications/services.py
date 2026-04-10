"""
Notification services for sending emails and creating in-app notifications.
"""
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.db.models import Q, F
from datetime import timedelta
import logging

from .models import (
    NotificationPreference, JobAlert, Notification, 
    NotificationDigest, EmailLog
)
from apps.recommendations.models import JobMatchScore
from apps.jobs.models import JobVacancy

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Core service for creating and sending notifications.
    """
    
    @classmethod
    def create_job_match_notification(cls, user, job, match_score):
        """
        Create a notification for a job match.
        Only creates if user preferences allow.
        """
        # Check user preferences
        try:
            prefs = user.notification_preferences
        except NotificationPreference.DoesNotExist:
            prefs = NotificationPreference.objects.create(user=user)
        
        # Check match threshold
        if match_score.match_score < prefs.match_threshold:
            return None
        
        # Check if notification already exists for this job
        existing = Notification.objects.filter(
            user=user,
            job=job,
            type=Notification.NotificationType.JOB_MATCH,
            created_at__gte=timezone.now() - timedelta(days=1)
        ).exists()
        
        if existing:
            return None
        
        # Determine delivery method
        delivery_method = Notification.DeliveryMethod.IN_APP
        if prefs.email_enabled and prefs.email_frequency == 'INSTANT':
            if prefs.should_send_email_now():
                delivery_method = Notification.DeliveryMethod.BOTH
        
        # Create notification
        notification = Notification.objects.create(
            user=user,
            type=Notification.NotificationType.JOB_MATCH,
            title=f"New Job Match: {job.title}",
            message=cls._generate_match_message(job, match_score),
            job=job,
            delivery_method=delivery_method,
            match_score=match_score.match_score
        )
        
        # Send email if instant
        if delivery_method in [Notification.DeliveryMethod.EMAIL, Notification.DeliveryMethod.BOTH]:
            cls.send_single_notification_email(notification)
        
        return notification
    
    @classmethod
    def _generate_match_message(cls, job, match_score):
        """Generate human-readable match message."""
        return f"""
        We found a job that matches your profile ({match_score.match_score:.0f}% match).
        
        {job.title} at {job.company_name}
        Location: {job.location_display}
        
        {match_score.match_reason}
        """.strip()
    
    @classmethod
    def send_single_notification_email(cls, notification):
        """Send a single notification email."""
        if notification.is_sent:
            return
        
        user = notification.user
        
        # Create email log
        email_log = EmailLog.objects.create(
            user=user,
            email_type=EmailLog.EmailType.ALERT,
            recipient=user.email,
            subject=notification.title,
            job_count=1
        )
        
        try:
            # Render email template
            html_content = render_to_string('notifications/emails/single_alert.html', {
                'user': user,
                'notification': notification,
                'job': notification.job,
                'site_name': settings.SITE_NAME,
                'site_url': settings.SITE_URL,
            })
            
            # Send email
            msg = EmailMultiAlternatives(
                subject=notification.title,
                body=notification.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            # Update status
            notification.mark_as_sent()
            email_log.status = 'SENT'
            email_log.sent_at = timezone.now()
            email_log.save()
            
        except Exception as e:
            logger.error(f"Failed to send email to {user.email}: {e}")
            email_log.status = 'FAILED'
            email_log.error_message = str(e)
            email_log.save()
    
    @classmethod
    def process_job_alerts(cls, frequency='DAILY'):
        """
        Process job alerts for users with specified frequency.
        Should be run via cron job.
        """
        alerts = JobAlert.objects.filter(
            is_active=True,
            frequency=frequency
        ).select_related('user', 'category')
        
        alerts_processed = 0
        jobs_found_total = 0
        
        for alert in alerts:
            # Determine time period
            if alert.last_triggered:
                since = alert.last_triggered
            elif frequency == 'DAILY':
                since = timezone.now() - timedelta(days=1)
            else:  # WEEKLY
                since = timezone.now() - timedelta(days=7)
            
            # Get matching jobs
            matching_jobs = alert.get_matching_jobs(since=since)
            job_count = matching_jobs.count()
            
            if job_count > 0:
                # Create notification
                notification = Notification.objects.create(
                    user=alert.user,
                    type=Notification.NotificationType.JOB_ALERT,
                    title=f"Job Alert: {alert.name}",
                    message=f"Found {job_count} new jobs matching your alert '{alert.name}'.",
                    job_alert=alert
                )
                
                # Update alert stats
                alert.last_triggered = timezone.now()
                alert.jobs_found_last_trigger = job_count
                alert.total_jobs_found = F('total_jobs_found') + job_count
                alert.save(update_fields=['last_triggered', 'jobs_found_last_trigger', 'total_jobs_found'])
                
                # Send email if user has email enabled
                try:
                    prefs = alert.user.notification_preferences
                    if prefs.email_enabled:
                        cls.send_alert_digest_email(alert.user, alert, matching_jobs[:10])
                except NotificationPreference.DoesNotExist:
                    pass
                
                alerts_processed += 1
                jobs_found_total += job_count
        
        return alerts_processed, jobs_found_total
    
    @classmethod
    def send_alert_digest_email(cls, user, alert, jobs):
        """Send email digest for a job alert."""
        email_log = EmailLog.objects.create(
            user=user,
            email_type=EmailLog.EmailType.ALERT,
            recipient=user.email,
            subject=f"Job Alert: {alert.name}",
            job_count=len(jobs)
        )
        
        try:
            html_content = render_to_string('notifications/emails/alert_digest.html', {
                'user': user,
                'alert': alert,
                'jobs': jobs,
                'site_name': settings.SITE_NAME,
                'site_url': settings.SITE_URL,
            })
            
            msg = EmailMultiAlternatives(
                subject=f"[{alert.name}] {len(jobs)} new jobs found",
                body=f"Found {len(jobs)} new jobs matching your alert.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            email_log.status = 'SENT'
            email_log.sent_at = timezone.now()
            email_log.save()
            
        except Exception as e:
            logger.error(f"Failed to send alert digest to {user.email}: {e}")
            email_log.status = 'FAILED'
            email_log.error_message = str(e)
            email_log.save()
    
    @classmethod
    def create_daily_digests(cls):
        """
        Create daily digests for all users with daily frequency.
        Run at end of day.
        """
        users_with_daily = NotificationPreference.objects.filter(
            email_enabled=True,
            email_frequency='DAILY'
        ).select_related('user')
        
        period_end = timezone.now().replace(hour=23, minute=59, second=59)
        period_start = period_end - timedelta(days=1)
        
        digests_created = 0
        
        for pref in users_with_daily:
            user = pref.user
            
            # Get pending notifications from last 24 hours
            notifications = Notification.objects.filter(
                user=user,
                created_at__gte=period_start,
                created_at__lte=period_end,
                delivery_method__in=['EMAIL', 'BOTH']
            ).exclude(
                type=Notification.NotificationType.SYSTEM
            )
            
            # Also get high-match jobs that weren't notified
            high_match_jobs = JobMatchScore.objects.filter(
                user=user,
                match_score__gte=pref.match_threshold,
                calculated_at__gte=period_start
            ).exclude(
                job__in=notifications.values('job')
            ).select_related('job')
            
            total_notifications = notifications.count() + high_match_jobs.count()
            
            if total_notifications > 0:
                # Create digest
                digest = NotificationDigest.objects.create(
                    user=user,
                    digest_type=NotificationDigest.DigestType.DAILY,
                    period_start=period_start,
                    period_end=period_end,
                    notification_count=total_notifications,
                    new_jobs_count=high_match_jobs.count(),
                    job_matches_count=notifications.filter(type='JOB_MATCH').count()
                )
                
                digest.notifications.set(notifications)
                digests_created += 1
                
                # Send digest email
                cls.send_digest_email(digest, list(notifications), list(high_match_jobs))
        
        return digests_created
    
    @classmethod
    def send_digest_email(cls, digest, notifications, high_match_jobs):
        """Send a digest email."""
        user = digest.user
        
        email_log = EmailLog.objects.create(
            user=user,
            email_type=EmailLog.EmailType.DIGEST,
            recipient=user.email,
            subject=f"Your Daily Job Digest - {digest.period_end.date()}",
            job_count=digest.new_jobs_count
        )
        
        try:
            html_content = render_to_string('notifications/emails/daily_digest.html', {
                'user': user,
                'digest': digest,
                'notifications': notifications,
                'high_match_jobs': [m.job for m in high_match_jobs[:5]],
                'site_name': settings.SITE_NAME,
                'site_url': settings.SITE_URL,
            })
            
            msg = EmailMultiAlternatives(
                subject=f"Your Daily Job Digest - {digest.new_jobs_count} new matches",
                body=f"View your daily job matches and updates.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            digest.is_sent = True
            digest.sent_at = timezone.now()
            digest.save(update_fields=['is_sent', 'sent_at'])
            
            email_log.status = 'SENT'
            email_log.sent_at = timezone.now()
            email_log.save()
            
        except Exception as e:
            logger.error(f"Failed to send digest to {user.email}: {e}")
            email_log.status = 'FAILED'
            email_log.error_message = str(e)
            email_log.save()


class NotificationSignalHandler:
    """
    Signal handlers for automatic notifications.
    """
    
    @staticmethod
    def on_job_created(job):
        """
        When a new job is approved, check for matching users.
        """
        if not job.is_approved:
            return
        
        # Get users with instant notifications enabled
        instant_prefs = NotificationPreference.objects.filter(
            email_frequency='INSTANT',
            email_enabled=True
        ).select_related('user')
        
        notifications_created = 0
        
        for pref in instant_prefs:
            # Check if job matches user's profile
            from apps.recommendations.matching_engine import JobMatchingEngine
            
            engine = JobMatchingEngine(pref.user)
            # Quick match calculation
            skill_score = engine._simple_skill_match(
                pref.user.profile.skills,
                [job.required_skills]
            )[0] if pref.user.profile.skills else 0
            
            if skill_score * 100 >= pref.match_threshold:
                # Create match score record
                match_score, _ = JobMatchScore.objects.get_or_create(
                    user=pref.user,
                    job=job,
                    defaults={
                        'match_score': skill_score * 100,
                        'skill_match_score': skill_score * 100,
                    }
                )
                
                # Create notification
                NotificationService.create_job_match_notification(
                    pref.user, job, match_score
                )
                notifications_created += 1
        
        return notifications_created