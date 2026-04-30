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
    
    # Add pending approvals count for staff users
    if request.user.is_authenticated and request.user.is_staff:
        try:
            from apps.jobs.models import JobVacancy
            pending_count = JobVacancy.objects.filter(
                is_approved=False
            ).count()
            context['pending_approvals'] = pending_count
        except:
            context['pending_approvals'] = 0
    
    return context