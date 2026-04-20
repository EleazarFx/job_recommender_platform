"""
Django Admin configuration for Ingestion app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import DataSource, IngestionJob


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    """Data Source admin configuration."""
    
    list_display = ['name', 'source_type', 'is_active', 'sync_frequency', 'last_sync_status_badge', 'last_sync']
    list_filter = ['source_type', 'sync_frequency', 'is_active', 'last_sync_status']
    search_fields = ['name', 'url']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'source_type', 'url', 'is_active')
        }),
        ('Authentication', {
            'fields': ('auth_type', 'api_key', 'api_secret'),
            'classes': ('collapse',)
        }),
        ('Scheduling', {
            'fields': ('sync_frequency',)
        }),
        ('Trust Settings', {
            'fields': ('default_trust_score', 'auto_approve')
        }),
        ('Field Mapping', {
            'fields': ('field_mapping',),
            'classes': ('collapse',),
            'description': 'JSON mapping of source fields to model fields'
        }),
        ('Status', {
            'fields': ('last_sync', 'last_sync_status')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_sync', 'last_sync_status']
    
    def last_sync_status_badge(self, obj):
        """Display sync status with color."""
        if obj.last_sync_status == 'SUCCESS':
            color = 'green'
            icon = '✅'
        elif obj.last_sync_status == 'FAILED':
            color = 'red'
            icon = '❌'
        elif obj.last_sync_status == 'RUNNING':
            color = 'blue'
            icon = '🔄'
        else:
            return '-'
        
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, obj.last_sync_status
        )
    last_sync_status_badge.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    """Ingestion Job admin for monitoring imports."""
    
    list_display = ['id', 'source_info', 'status_badge', 'progress', 'started_at', 'created_by']
    list_filter = ['status', 'started_at', 'created_at']
    search_fields = ['data_source__name', 'created_by__email']
    raw_id_fields = ['data_source', 'created_by']
    
    fieldsets = (
        (None, {
            'fields': ('data_source', 'uploaded_file', 'status')
        }),
        ('Progress', {
            'fields': ('total_records', 'processed_records', 'created_records', 'updated_records', 'failed_records')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at')
        }),
        ('Errors', {
            'fields': ('error_log',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at')
        }),
    )
    
    readonly_fields = [
        'total_records', 'processed_records', 'created_records',
        'updated_records', 'failed_records', 'started_at', 'completed_at',
        'error_log', 'created_at'
    ]
    
    def source_info(self, obj):
        """Display data source or file info."""
        if obj.data_source:
            return obj.data_source.name
        elif obj.uploaded_file:
            return obj.uploaded_file.name.split('/')[-1]
        return 'Manual'
    source_info.short_description = 'Source'
    
    def status_badge(self, obj):
        colors = {
            'COMPLETED': 'green',
            'PROCESSING': 'blue',
            'PENDING': 'orange',
            'FAILED': 'red',
            'PARTIAL': 'yellow'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def progress(self, obj):
        """Display progress bar."""
        if obj.total_records > 0:
            percentage = (obj.processed_records / obj.total_records) * 100
            return format_html(
                '<progress value="{}" max="100" style="width: 100px;"></progress> {:.0f}%',
                percentage, percentage
            )
        return '-'
    progress.short_description = 'Progress'
    
    def has_add_permission(self, request):
        return False