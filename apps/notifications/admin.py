"""
Django Admin configuration for Notifications app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    NotificationPreference, JobAlert, Notification,
    NotificationDigest, EmailLog
)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Notification preferences admin."""
    
    list_display = ['user', 'email_enabled', 'email_frequency', 'match_threshold', 'last_notification_sent']
    list_filter = ['email_enabled', 'email_frequency', 'notify_malawi_only']
    search_fields = ['user__email']
    raw_id_fields = ['user']
    
    fieldsets = (
        ('Channels', {
            'fields': ('email_enabled', 'in_app_enabled')
        }),
        ('Email Settings', {
            'fields': ('email_frequency', 'match_threshold')
        }),
        ('Location Preferences', {
            'fields': ('notify_malawi_only', 'preferred_locations_filter')
        }),
        ('Quiet Hours', {
            'fields': ('quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end')
        }),
        ('Tracking', {
            'fields': ('last_notification_sent', 'created_at', 'updated_at')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_notification_sent']


@admin.register(JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    """Job Alerts admin."""
    
    list_display = ['name', 'user', 'frequency', 'is_active', 'last_triggered', 'total_jobs_found']
    list_filter = ['frequency', 'is_active', 'created_at']
    search_fields = ['name', 'user__email', 'keywords', 'location']
    raw_id_fields = ['user', 'category']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'user', 'is_active')
        }),
        ('Search Criteria', {
            'fields': ('keywords', 'location', 'job_types', 'experience_level', 'category')
        }),
        ('Schedule', {
            'fields': ('frequency',)
        }),
        ('Statistics', {
            'fields': ('last_triggered', 'jobs_found_last_trigger', 'total_jobs_found'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['last_triggered', 'jobs_found_last_trigger', 'total_jobs_found']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Notifications admin."""
    
    list_display = ['user', 'type', 'title_preview', 'is_read', 'is_sent', 'created_at']
    list_filter = ['type', 'delivery_method', 'is_read', 'is_sent', 'created_at']
    search_fields = ['user__email', 'title', 'message']
    raw_id_fields = ['user', 'job', 'job_alert']
    
    fieldsets = (
        (None, {
            'fields': ('user', 'type', 'title', 'message')
        }),
        ('Related Objects', {
            'fields': ('job', 'job_alert')
        }),
        ('Delivery', {
            'fields': ('delivery_method', 'match_score')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'is_sent', 'sent_at')
        }),
        ('Scheduling', {
            'fields': ('scheduled_for', 'created_at')
        }),
    )
    
    readonly_fields = ['created_at', 'read_at', 'sent_at']
    
    def title_preview(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_preview.short_description = 'Title'


@admin.register(NotificationDigest)
class NotificationDigestAdmin(admin.ModelAdmin):
    """Notification digests admin."""
    
    list_display = ['user', 'digest_type', 'notification_count', 'is_sent', 'period_end']
    list_filter = ['digest_type', 'is_sent', 'is_read', 'period_end']
    search_fields = ['user__email']
    raw_id_fields = ['user']
    filter_horizontal = ['notifications']
    
    readonly_fields = [
        'period_start', 'period_end', 'created_at', 'sent_at',
        'notification_count', 'new_jobs_count', 'job_matches_count'
    ]


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    """Email log for monitoring."""
    
    list_display = ['recipient', 'email_type', 'status_badge', 'subject', 'created_at']
    list_filter = ['email_type', 'status', 'created_at']
    search_fields = ['recipient', 'subject', 'user__email']
    raw_id_fields = ['user']
    
    readonly_fields = [
        'user', 'email_type', 'recipient', 'subject', 'job_count',
        'status', 'error_message', 'sent_at', 'created_at'
    ]
    
    def status_badge(self, obj):
        colors = {
            'SENT': 'green',
            'PENDING': 'orange',
            'FAILED': 'red',
            'BOUNCED': 'purple'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def has_add_permission(self, request):
        return False