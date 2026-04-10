"""
App configuration for Accounts app.
"""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = 'User Accounts & Authentication'
    
    def ready(self):
        """Import signals when app is ready."""
        import apps.accounts.signals