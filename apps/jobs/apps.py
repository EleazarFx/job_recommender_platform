from django.apps import AppConfig


class JobsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.jobs'
    verbose_name = 'Job Management'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.jobs.signals
        except ImportError:
            pass