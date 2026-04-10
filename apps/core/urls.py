"""
URL patterns for core pages (homepage, about, etc.)
"""
from django.urls import path
from django.views.generic import TemplateView

app_name = 'core'

urlpatterns = [
    # Homepage (will be updated later with real view)
    path('', TemplateView.as_view(template_name='core/home.html'), name='home'),
    
    # Static pages
    path('about/', TemplateView.as_view(template_name='core/about.html'), name='about'),
    path('privacy/', TemplateView.as_view(template_name='core/privacy.html'), name='privacy'),
    path('terms/', TemplateView.as_view(template_name='core/terms.html'), name='terms'),
]