"""
Main URL Configuration for Job Recommendation Platform.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django Admin (We'll customize this later)
    path('admin/', admin.site.urls),
    
    # Custom Apps URLs (We'll create these files progressively)
    path('', include('apps.core.urls', namespace='core')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('jobs/', include('apps.jobs.urls', namespace='jobs')),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),

    path('recommendations/', include('apps.recommendations.urls', namespace='recommendations')),

    #path('interactions/', include('apps.interactions.urls', namespace='interactions')),
    #path('ingestion/', include('apps.ingestion.urls', namespace='ingestion')),
    

]

# Serve media files in development ONLY
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Django Debug Toolbar
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass