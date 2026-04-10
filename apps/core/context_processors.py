"""
Context processor to inject site-wide data into all templates.
"""
from django.conf import settings

def site_settings(request):
    """Add site settings to template context."""
    return {
        'SITE_NAME': 'Malawi Job Connect',
        'SITE_TAGLINE': 'Find Your Next Opportunity',
        'CURRENT_YEAR': 2026,
        'DEBUG': settings.DEBUG,
    }