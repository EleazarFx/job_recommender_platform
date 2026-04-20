"""
Django Admin configuration for Interactions app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import JobApplication


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    """Job Applications admin."""
    
    list_display = ['applicant', 'job_link', 'status_badge', 'applied_at']
    list_filter = ['status', 'applied_at']
    search_fields = ['applicant__email', 'job__title', 'job__company_name']
    raw_id_fields = ['job', 'applicant']
    
    fieldsets = (
        (None, {
            'fields': ('job', 'applicant', 'status')
        }),
        ('Application Details', {
            'fields': ('cover_letter',)
        }),
        ('Employer Feedback', {
            'fields': ('employer_notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('applied_at', 'updated_at')
        }),
    )
    
    readonly_fields = ['applied_at', 'updated_at']
    
    def job_link(self, obj):
        url = reverse('admin:jobs_jobvacancy_change', args=[obj.job.id])
        return format_html('<a href="{}">{} at {}</a>', url, obj.job.title, obj.job.company_name)
    job_link.short_description = 'Job'
    job_link.admin_order_field = 'job__title'
    
    def status_badge(self, obj):
        colors = {
            'APPLIED': 'blue',
            'REVIEWED': 'orange',
            'SHORTLISTED': 'purple',
            'INTERVIEW': 'teal',
            'OFFER': 'green',
            'REJECTED': 'red',
            'WITHDRAWN': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'