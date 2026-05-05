"""
Context processor to inject site-wide data into all templates.
"""
from django.conf import settings
from django.utils import timezone


def site_settings(request):
    """Add site settings to template context."""
    context = {
        'SITE_NAME': settings.SITE_NAME,
        'SITE_TAGLINE': settings.SITE_TAGLINE,
        'CURRENT_YEAR': timezone.now().year,
        'DEBUG': settings.DEBUG,
    }
    
    # Add pending approvals and employer verification counts for staff users
    if request.user.is_authenticated and request.user.is_staff:
        try:
            from apps.jobs.models import JobVacancy
            from apps.accounts.models import User

            pending_count = JobVacancy.objects.filter(
                is_approved=False
            ).count()
            pending_employer_verifications = User.objects.filter(
                user_type='EMPLOYER',
                is_verified_employer=False
            ).count()

            context['pending_approvals'] = pending_count
            context['pending_verifications'] = pending_employer_verifications
        except Exception:
            context['pending_approvals'] = 0
            context['pending_verifications'] = 0
    
    return context