"""
Django Admin configuration for Jobs app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta  # ADD THIS IMPORT
from .models import JobCategory, JobVacancy, JobReport, JobView, SavedJob


# ============================================
# INLINE CLASSES (Define BEFORE they're used)
# ============================================

class JobReportInline(admin.TabularInline):
    """
    Inline reports for job vacancies.
    Displays reports directly in the JobVacancy admin page.
    """
    model = JobReport
    extra = 0  # Don't show empty forms
    readonly_fields = ['reported_by', 'reason', 'details', 'created_at']
    can_delete = False
    show_change_link = True
    
    fields = ['reported_by', 'reason', 'details', 'created_at', 'reviewed']
    
    def has_add_permission(self, request, obj=None):
        """Prevent adding reports manually through inline."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Allow viewing but not editing."""
        return False


# ============================================
# JOB CATEGORY ADMIN
# ============================================

@admin.register(JobCategory)
class JobCategoryAdmin(admin.ModelAdmin):
    """Job Category admin configuration."""
    
    list_display = ['name', 'icon_preview', 'active_jobs_count', 'is_active', 'display_order']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ['name']}
    list_editable = ['is_active', 'display_order']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description')
        }),
        ('Display Settings', {
            'fields': ('icon', 'is_active', 'display_order')
        }),
    )
    
    def icon_preview(self, obj):
        """Preview Font Awesome icon."""
        if obj.icon:
            return format_html('<i class="fas {}"></i>', obj.icon)
        return '-'
    icon_preview.short_description = 'Icon'
    
    def active_jobs_count(self, obj):
        """Show count of active jobs in this category."""
        count = obj.get_job_count()
        if count > 0:
            url = reverse('admin:jobs_jobvacancy_changelist') + f'?category__id__exact={obj.id}'
            return format_html('<a href="{}">{} jobs</a>', url, count)
        return '0 jobs'
    active_jobs_count.short_description = 'Active Jobs'


# ============================================
# JOB VACANCY ADMIN (Uses JobReportInline)
# ============================================

@admin.register(JobVacancy)
class JobVacancyAdmin(admin.ModelAdmin):
    """Job Vacancy admin configuration."""
    
    inlines = [JobReportInline]  # Now this is properly defined above
    
    list_display = [
        'title', 'company_name', 'location_display', 'job_type', 
        'experience_level', 'trust_score_badge', 'is_approved', 
        'expiry_status', 'date_posted'
    ]
    
    list_filter = [
        'is_approved', 'job_type', 'experience_level', 'location_type',
        'source_type', 'is_verified_company', 'category', 'date_posted'
    ]
    
    search_fields = ['title', 'company_name', 'description', 'required_skills', 'location_display']
    
    list_editable = ['is_approved']
    
    actions = ['approve_jobs', 'extend_expiry_30_days', 'mark_as_verified']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'company_name', 'company_logo', 'company_website')
        }),
        ('Category & Description', {
            'fields': ('category', 'description', 'requirements', 'responsibilities')
        }),
        ('Skills & Experience', {
            'fields': ('required_skills', 'required_qualifications', 'experience_level', 'years_of_experience_required')
        }),
        ('Location', {
            'fields': ('location_type', 'city', 'district', 'country', 'location_display', 'is_remote')
        }),
        ('Job Details', {
            'fields': ('job_type', 'salary_min', 'salary_max', 'salary_currency', 'salary_is_displayed')
        }),
        ('Application', {
            'fields': ('application_url', 'application_email', 'application_deadline')
        }),
        ('Trust & Verification', {
            'fields': ('source_type', 'trust_score', 'is_approved', 'is_verified_company', 'has_suspicious_content', 'report_count')
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at'),
            'classes': ('collapse',)
        }),
        ('Dates & Expiry', {
            'fields': ('date_posted', 'date_updated', 'expiry_date', 'external_id', 'source_url'),
        }),
        ('Poster Information', {
            'fields': ('posted_by',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('view_count', 'application_count', 'save_count'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'date_posted', 'date_updated', 'approved_at', 'view_count', 
        'application_count', 'save_count', 'report_count'
    ]
    
    raw_id_fields = ['posted_by', 'approved_by', 'category']
    
    def trust_score_badge(self, obj):
        """Display trust score with color coding."""
        score = obj.trust_score
        
        if score >= 80:
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} {}%</span>',
                'green', '✅', score
            )
        elif score >= 50:
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} {}%</span>',
                'orange', '⚠️', score
            )
        else:
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} {}%</span>',
                'red', '❌', score
            )
    trust_score_badge.short_description = 'Trust'
    trust_score_badge.admin_order_field = 'trust_score'
    
    def expiry_status(self, obj):
        """Display expiry status with visual indicator."""
        if obj.is_expired():
            return format_html(
                '<span style="color: {};">{} {}</span>',
                'red', '❌', 'Expired'
            )
        elif obj.expiry_date <= timezone.now().date() + timedelta(days=7):
            return format_html(
                '<span style="color: {};">{} {}</span>',
                'orange', '⚠️', 'Expires soon'
            )
        else:
            return format_html(
                '<span style="color: {};">{} {}</span>',
                'green', '✅', 'Active'
            )
    expiry_status.short_description = 'Status'
    expiry_status.admin_order_field = 'expiry_date'
    
    # Custom Admin Actions
    @admin.action(description="Approve selected jobs")
    def approve_jobs(self, request, queryset):
        updated = queryset.update(
            is_approved=True,
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f'{updated} job(s) approved successfully.')
    
    @admin.action(description="Extend expiry by 30 days")
    def extend_expiry_30_days(self, request, queryset):
        updated = 0
        for job in queryset:
            job.expiry_date = timezone.now().date() + timedelta(days=30)
            job.save(update_fields=['expiry_date'])
            updated += 1
        
        self.message_user(request, f'{updated} job(s) extended by 30 days.')
    
    @admin.action(description="Mark as verified company")
    def mark_as_verified(self, request, queryset):
        updated = queryset.update(is_verified_company=True, trust_score=85)
        self.message_user(request, f'{updated} job(s) marked as verified companies.')


# ============================================
# JOB REPORT ADMIN
# ============================================

@admin.register(JobReport)
class JobReportAdmin(admin.ModelAdmin):
    """Job Report admin for moderation."""
    
    list_display = ['job_link', 'reported_by', 'reason', 'reviewed', 'created_at']
    list_filter = ['reason', 'reviewed', 'created_at']
    search_fields = ['job__title', 'job__company_name', 'reported_by__email', 'details']
    readonly_fields = ['job', 'reported_by', 'reason', 'details', 'report_count_at_time', 'created_at']
    
    fieldsets = (
        (None, {
            'fields': ('job', 'reported_by', 'reason', 'details')
        }),
        ('Review Status', {
            'fields': ('reviewed', 'reviewed_by', 'reviewed_at')
        }),
        ('Metadata', {
            'fields': ('report_count_at_time', 'created_at')
        }),
    )
    
    def job_link(self, obj):
        """Link to the reported job."""
        url = reverse('admin:jobs_jobvacancy_change', args=[obj.job.id])
        return format_html('<a href="{}">{}</a>', url, obj.job.title)
    job_link.short_description = 'Job'
    
    def save_model(self, request, obj, form, change):
        """Track who reviewed the report."""
        if obj.reviewed and not obj.reviewed_by:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)
    
    actions = ['mark_as_reviewed']
    
    @admin.action(description="Mark selected reports as reviewed")
    def mark_as_reviewed(self, request, queryset):
        updated = queryset.update(
            reviewed=True,
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f'{updated} report(s) marked as reviewed.')


# ============================================
# JOB VIEW ADMIN
# ============================================

@admin.register(JobView)
class JobViewAdmin(admin.ModelAdmin):
    """Job View analytics."""
    
    list_display = ['job', 'user', 'viewed_at', 'ip_address']
    list_filter = ['viewed_at']
    search_fields = ['job__title', 'user__email', 'ip_address']
    readonly_fields = ['job', 'user', 'viewed_at', 'ip_address', 'session_key']
    
    def has_add_permission(self, request):
        return False


# ============================================
# SAVED JOB ADMIN
# ============================================

@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    """Saved Jobs admin."""
    
    list_display = ['user', 'job_link', 'saved_at']
    list_filter = ['saved_at']
    search_fields = ['user__email', 'job__title', 'job__company_name']
    raw_id_fields = ['user', 'job']
    readonly_fields = ['saved_at']
    
    def job_link(self, obj):
        url = reverse('admin:jobs_jobvacancy_change', args=[obj.job.id])
        return format_html('<a href="{}">{} at {}</a>', url, obj.job.title, obj.job.company_name)
    job_link.short_description = 'Job'