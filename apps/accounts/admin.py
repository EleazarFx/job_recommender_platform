"""
Django Admin configuration for Accounts app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from .models import User, Profile, PasswordResetOTP, LoginAttempt, AdminAuditLog


class ProfileInline(admin.StackedInline):
    """Inline profile editing in User admin."""
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    fieldsets = (
        (None, {
            'fields': ('avatar', 'skills', 'qualifications', 'experience_level')
        }),
        ('Preferences', {
            'fields': ('preferred_locations', 'preferred_job_types')
        }),
    )


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """Custom User Admin with email as primary identifier."""
    
    inlines = [ProfileInline]
    
    list_display = [
        'email', 'first_name', 'last_name', 'user_type', 
        'is_verified_employer', 'profile_completion', 'is_active', 
        'date_joined'
    ]
    
    list_filter = [
        'user_type', 'is_verified_employer', 'is_active', 
        'is_staff', 'is_superuser', 'date_joined'
    ]
    
    search_fields = ['email', 'first_name', 'last_name']
    
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name')
        }),
        ('Account Type & Verification', {
            'fields': ('user_type', 'is_verified_employer', 'profile_completion_percentage')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Notification Settings', {
            'fields': ('email_notifications', 'in_app_notifications'),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'user_type', 'password1', 'password2'),
        }),
    )
    
    def profile_completion(self, obj):
        """Display profile completion percentage with color coding."""
        percentage = obj.profile_completion_percentage
        
        if percentage >= 80:
            color = 'green'
        elif percentage >= 50:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, percentage
        )
    profile_completion.short_description = 'Profile Complete'
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields read-only after creation."""
        if obj:
            return ['email', 'date_joined', 'last_login']
        return []


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Profile admin configuration."""
    
    list_display = ['user', 'experience_level', 'years_of_experience', 'updated_at']
    list_filter = ['experience_level', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'skills']
    raw_id_fields = ['user']
    
    fieldsets = (
        (None, {
            'fields': ('user', 'avatar')
        }),
        ('Skills & Qualifications', {
            'fields': ('skills', 'qualifications', 'extracted_skills')
        }),
        ('Experience', {
            'fields': ('experience_level', 'years_of_experience')
        }),
        ('Preferences', {
            'fields': ('preferred_locations', 'preferred_job_types')
        }),
        ('CV Upload', {
            'fields': ('cv_file',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'extracted_skills']


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    """Password Reset OTP admin for monitoring."""
    
    list_display = ['user', 'code', 'created_at', 'expires_at', 'is_used', 'attempts']
    list_filter = ['is_used', 'created_at']
    search_fields = ['user__email', 'code']
    readonly_fields = ['code', 'created_at', 'expires_at', 'attempts']
    
    def has_add_permission(self, request):
        """Prevent manual creation of OTPs."""
        return False


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Login attempt monitoring for security."""
    
    list_display = ['email', 'ip_address', 'attempt_time', 'is_successful']
    list_filter = ['is_successful', 'attempt_time']
    search_fields = ['email', 'ip_address']
    readonly_fields = ['email', 'ip_address', 'attempt_time', 'is_successful']
    
    def has_add_permission(self, request):
        return False


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    """Audit log for admin actions."""
    
    list_display = ['action_type', 'performed_by', 'target_user', 'ip_address', 'created_at']
    list_filter = ['action_type', 'created_at']
    search_fields = ['performed_by__email', 'target_user__email', 'ip_address']
    readonly_fields = ['action_type', 'performed_by', 'target_user', 'details', 'ip_address', 'user_agent', 'created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False