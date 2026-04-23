"""
Admin dashboard views for managing jobs, users, and data ingestion.
Security: All views require staff or superuser access.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin
from datetime import timedelta
import json

from apps.jobs.forms import JobPostForm

from apps.jobs.models import JobVacancy, JobCategory, JobReport
from apps.accounts.models import User
from apps.ingestion.models import DataSource, IngestionJob
from apps.ingestion.forms import DataSourceForm, CSVUploadForm
from apps.ingestion.tasks import process_csv_upload, fetch_api_data


# ============================================
# CUSTOM DECORATORS
# ============================================

def superuser_required(view_func):
    """
    Decorator to restrict access to superusers only.
    Use this for critical admin functions like creating other admins.
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to continue.")
            return redirect('accounts:login')
        
        if not request.user.is_superuser:
            messages.error(request, "Superuser access required for this action.")
            return redirect('dashboard:home')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_or_staff_required(view_func):
    """
    Decorator that requires either superuser OR staff status.
    More flexible than @staff_member_required alone.
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to continue.")
            return redirect('accounts:login')
        
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "You do not have permission to access this area.")
            return redirect('core:home')
        
        return view_func(request, *args, **kwargs)
    return wrapper


# ============================================
# MIXINS FOR CLASS-BASED VIEWS
# ============================================

class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to staff/superusers only."""
    
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser)
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, 'Please log in to continue.')
            return redirect('accounts:login')
        
        messages.error(self.request, 'You do not have permission to access this area.')
        return redirect('core:home')


class SuperuserRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to superusers only."""
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, 'Please log in to continue.')
            return redirect('accounts:login')
        
        messages.error(self.request, 'Superuser access required.')
        return redirect('dashboard:home')


# ============================================
# DASHBOARD VIEWS
# ============================================

@staff_member_required(login_url='accounts:login')
def dashboard_home(request):
    """
    Main admin dashboard with statistics.
    Access: Staff and Superusers
    """
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Additional statistics
    active_jobs = JobVacancy.objects.filter(
        is_approved=True, 
        expiry_date__gte=today
    ).count()
    
    verified_employers = User.objects.filter(
        user_type='EMPLOYER', 
        is_verified_employer=True
    ).count()
    
    pending_verifications = User.objects.filter(
        user_type='EMPLOYER', 
        is_verified_employer=False
    ).count()
    
    # Jobs expiring soon (next 7 days)
    expiring_soon = JobVacancy.objects.filter(
        is_approved=True,
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=7)
    ).count()
    
    # Application statistics
    from apps.interactions.models import JobApplication
    total_applications = JobApplication.objects.count()
    applications_this_week = JobApplication.objects.filter(
        applied_at__date__gte=week_ago
    ).count()
    
    context = {
        'total_users': User.objects.count(),
        'new_users_week': User.objects.filter(date_joined__date__gte=week_ago).count(),
        'total_jobs': JobVacancy.objects.filter(is_approved=True).count(),
        'active_jobs': active_jobs,
        'pending_approvals': JobVacancy.objects.filter(is_approved=False).count(),
        'expired_jobs': JobVacancy.objects.filter(expiry_date__lt=today, is_approved=True).count(),
        'expiring_soon': expiring_soon,
        'total_reports': JobReport.objects.filter(reviewed=False).count(),
        'verified_employers': verified_employers,
        'pending_verifications': pending_verifications,
        'total_applications': total_applications,
        'applications_this_week': applications_this_week,
        'recent_jobs': JobVacancy.objects.order_by('-date_posted')[:10],
        'recent_users': User.objects.order_by('-date_joined')[:10],
        'pending_reports': JobReport.objects.filter(reviewed=False).select_related('job', 'reported_by')[:5],
        'jobs_by_category': JobCategory.objects.annotate(
            job_count=Count('jobs', filter=Q(jobs__is_approved=True))
        ).values('name', 'job_count'),
        'jobs_by_source': JobVacancy.objects.values('source_type').annotate(
            count=Count('id')
        ).order_by('-count'),
        'daily_jobs': JobVacancy.objects.filter(
            date_posted__date__gte=month_ago
        ).extra({'date': "date(date_posted)"}).values('date').annotate(
            count=Count('id')
        ).order_by('date'),
    }
    
    return render(request, 'dashboard/home.html', context)



@staff_member_required(login_url='accounts:login')
def ingestion_dashboard(request):
    """
    Data ingestion management page.
    Access: Staff and Superusers
    """
    data_sources = DataSource.objects.all().order_by('-is_active', 'name')
    recent_jobs = IngestionJob.objects.select_related('data_source', 'created_by').order_by('-created_at')[:20]
    
    context = {
        'data_sources': data_sources,
        'recent_jobs': recent_jobs,
        'csv_form': CSVUploadForm(),
        'source_form': DataSourceForm(),
    }
    
    return render(request, 'dashboard/ingestion.html', context)


@staff_member_required(login_url='accounts:login')
@require_POST
def upload_csv(request):
    """
    Handle CSV file upload with column mapping.
    Access: Staff and Superusers
    Method: POST only
    """
    form = CSVUploadForm(request.POST, request.FILES)
    
    if form.is_valid():
        ingestion_job = form.save(commit=False)
        ingestion_job.created_by = request.user
        ingestion_job.status = IngestionJob.Status.PENDING
        ingestion_job.save()
        
        column_mapping = json.loads(form.cleaned_data['column_mapping'])
        
        process_csv_upload(
            ingestion_job.id,
            column_mapping,
            trust_score=95,
            auto_approve=True
        )
        
        messages.success(request, 'CSV upload started. Processing in background.')
        
        return JsonResponse({
            'success': True,
            'job_id': ingestion_job.id,
            'message': 'CSV processing started'
        })
    
    return JsonResponse({
        'success': False,
        'errors': form.errors
    })


@staff_member_required(login_url='accounts:login')
def preview_csv_columns(request):
    """
    Preview CSV columns for mapping.
    Access: Staff and Superusers
    """
    if request.method == 'POST' and request.FILES.get('csv_file'):
        import pandas as pd
        
        csv_file = request.FILES['csv_file']
        
        try:
            df = pd.read_csv(csv_file, nrows=5)
            columns = df.columns.tolist()
            sample_data = df.head(3).to_dict('records')
            
            return JsonResponse({
                'success': True,
                'columns': columns,
                'sample_data': sample_data
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'No file provided'})


@staff_member_required(login_url='accounts:login')
@require_POST
def trigger_sync(request, pk):
    """
    Manually trigger sync for a data source.
    Access: Staff and Superusers
    """
    data_source = get_object_or_404(DataSource, pk=pk)
    
    if data_source.source_type in ['API_JSON', 'API_XML']:
        fetch_api_data(data_source.id)
        messages.success(request, f'Sync triggered for {data_source.name}')
    else:
        messages.error(request, 'Manual sync only available for API sources')
    
    return redirect('dashboard:ingestion')


@staff_member_required(login_url='accounts:login')
def job_approval_queue(request):
    """
    View for approving/rejecting pending jobs.
    Access: Staff and Superusers
    """
    pending_jobs = JobVacancy.objects.filter(
        is_approved=False
    ).select_related('posted_by').order_by('-date_posted')
    
    paginator = Paginator(pending_jobs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_pending': pending_jobs.count(),
    }
    
    return render(request, 'dashboard/job_approval.html', context)


@staff_member_required(login_url='accounts:login')
@require_POST
def approve_job(request, pk):
    """
    Approve a pending job.
    Access: Staff and Superusers
    """
    job = get_object_or_404(JobVacancy, pk=pk, is_approved=False)
    
    job.is_approved = True
    job.approved_by = request.user
    job.approved_at = timezone.now()
    job.save()
    
    messages.success(request, f'Job "{job.title}" has been approved.')
    
    return JsonResponse({'success': True})


@staff_member_required(login_url='accounts:login')
@require_POST
def reject_job(request, pk):
    """
    Reject and delete a pending job.
    Access: Staff and Superusers
    """
    job = get_object_or_404(JobVacancy, pk=pk, is_approved=False)
    
    title = job.title
    job.delete()
    
    messages.warning(request, f'Job "{title}" has been rejected and deleted.')
    
    return JsonResponse({'success': True})


@staff_member_required(login_url='accounts:login')
def reports_dashboard(request):
    """
    View and manage job reports.
    Access: Staff and Superusers
    """
    reports = JobReport.objects.select_related(
        'job', 'reported_by'
    ).order_by('-created_at')
    
    filter_status = request.GET.get('status', 'pending')
    if filter_status == 'pending':
        reports = reports.filter(reviewed=False)
    elif filter_status == 'reviewed':
        reports = reports.filter(reviewed=True)
    
    paginator = Paginator(reports, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'filter_status': filter_status,
        'total_reports': reports.count(),
    }
    
    return render(request, 'dashboard/reports.html', context)


@staff_member_required(login_url='accounts:login')
@require_POST
def resolve_report(request, pk):
    """
    Mark a report as reviewed.
    Access: Staff and Superusers
    """
    report = get_object_or_404(JobReport, pk=pk)
    action = request.POST.get('action')
    
    if action == 'remove_job':
        report.job.delete()
        messages.success(request, 'Job has been removed.')
    elif action == 'flag_job':
        report.job.has_suspicious_content = True
        report.job.save()
        messages.warning(request, 'Job has been flagged as suspicious.')
    
    report.reviewed = True
    report.reviewed_by = request.user
    report.reviewed_at = timezone.now()
    report.save()
    
    return JsonResponse({'success': True})


# ============================================
# SUPERUSER-ONLY VIEWS (Critical Operations)
# ============================================

@superuser_required
@require_http_methods(["GET", "POST"])
def create_admin_user(request):
    """
    Create new admin user - SUPERUSER ONLY.
    This is a critical security function.
    """
    # This should be implemented with a proper form
    # For now, redirect to Django Admin
    messages.info(request, 'Please use the Django Admin to create admin users.')
    return redirect('admin:accounts_user_add')


@superuser_required
def system_settings(request):
    """
    System-wide settings - SUPERUSER ONLY.
    """
    # Placeholder for system settings view
    messages.info(request, 'System settings coming soon.')
    return redirect('dashboard:home')


# ============================================
# CLASS-BASED VIEWS
# ============================================

class DataSourceCreateView(AdminRequiredMixin, CreateView):
    """Create new data source - Staff/Superuser only."""
    model = DataSource
    form_class = DataSourceForm
    template_name = 'dashboard/datasource_form.html'
    success_url = reverse_lazy('dashboard:ingestion')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Data source created successfully.')
        return super().form_valid(form)


class DataSourceUpdateView(AdminRequiredMixin, UpdateView):
    """Update data source - Staff/Superuser only."""
    model = DataSource
    form_class = DataSourceForm
    template_name = 'dashboard/datasource_form.html'
    success_url = reverse_lazy('dashboard:ingestion')
    
    def form_valid(self, form):
        messages.success(self.request, 'Data source updated successfully.')
        return super().form_valid(form)


# ============================================
# ADMIN JOB POSTING (Quick Add)
# ============================================

@staff_member_required(login_url='accounts:login')
def admin_create_job(request):
    """
    Admin form to quickly create a new job.
    Access: Staff and Superusers
    """
    from apps.jobs.forms import JobPostForm
    
    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.posted_by = request.user
            job.source_type = JobVacancy.SourceType.ADMIN_CSV
            job.trust_score = 95
            job.is_approved = True
            job.save()
            
            messages.success(request, f'Job "{job.title}" created successfully!')
            return redirect('dashboard:home')
    else:
        form = JobPostForm()
    
    context = {
        'form': form,
        'title': 'Create New Job (Admin)',
    }
    
    return render(request, 'dashboard/admin_create_job.html', context)




# Add these imports at the top
from apps.interactions.models import JobApplication



# ============================================
# EMPLOYER VERIFICATION VIEWS
# ============================================

@staff_member_required(login_url='accounts:login')
def employer_verification_queue(request):
    """
    View for verifying employer accounts.
    Access: Staff and Superusers
    """
    pending_employers = User.objects.filter(
        user_type='EMPLOYER',
        is_verified_employer=False
    ).select_related('profile').order_by('-date_joined')
    
    verified_employers = User.objects.filter(
        user_type='EMPLOYER',
        is_verified_employer=True
    ).select_related('profile').order_by('-date_joined')
    
    context = {
        'pending_employers': pending_employers,
        'verified_employers': verified_employers,
        'total_pending': pending_employers.count(),
        'total_verified': verified_employers.count(),
    }
    
    return render(request, 'dashboard/employer_verification.html', context)


@staff_member_required(login_url='accounts:login')
@require_POST
def verify_employer(request, pk):
    """
    Verify an employer account.
    Access: Staff and Superusers
    """
    employer = get_object_or_404(User, pk=pk, user_type='EMPLOYER')
    
    employer.is_verified_employer = True
    employer.save(update_fields=['is_verified_employer'])
    
    messages.success(request, f'Employer "{employer.email}" has been verified.')
    
    return JsonResponse({'success': True})


@staff_member_required(login_url='accounts:login')
@require_POST
def unverify_employer(request, pk):
    """
    Remove verification from an employer account.
    Access: Staff and Superusers
    """
    employer = get_object_or_404(User, pk=pk, user_type='EMPLOYER')
    
    employer.is_verified_employer = False
    employer.save(update_fields=['is_verified_employer'])
    
    messages.warning(request, f'Verification removed from "{employer.email}".')
    
    return JsonResponse({'success': True})






# ============================================
# ANALYTICS DASHBOARD
# ============================================

@staff_member_required(login_url='accounts:login')
def analytics_dashboard(request):
    """
    Advanced analytics dashboard.
    Access: Staff and Superusers
    """
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    # User growth over time
    user_growth = User.objects.filter(
        date_joined__date__gte=thirty_days_ago
    ).extra({'date': "date(date_joined)"}).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Job postings over time
    job_postings = JobVacancy.objects.filter(
        date_posted__date__gte=thirty_days_ago
    ).extra({'date': "date(date_posted)"}).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Top categories
    top_categories = JobCategory.objects.annotate(
        job_count=Count('jobs', filter=Q(jobs__is_approved=True))
    ).filter(job_count__gt=0).order_by('-job_count')[:10]
    
    # Top locations
    from django.db.models import Count
    top_locations = JobVacancy.objects.filter(
        is_approved=True
    ).values('city').annotate(
        count=Count('id')
    ).exclude(city='').order_by('-count')[:10]
    
    # User type distribution
    user_distribution = User.objects.values('user_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    context = {
        'user_growth': list(user_growth),
        'job_postings': list(job_postings),
        'top_categories': top_categories,
        'top_locations': top_locations,
        'user_distribution': user_distribution,
        'date_range': f"{thirty_days_ago} to {today}",
    }
    
    return render(request, 'dashboard/analytics.html', context)

# ============================================
# BULK ACTIONS
# ============================================

@staff_member_required(login_url='accounts:login')
@require_POST
def bulk_approve_jobs(request):
    """
    Bulk approve multiple pending jobs.
    Access: Staff and Superusers
    """
    job_ids = request.POST.getlist('job_ids')
    
    if not job_ids:
        return JsonResponse({'success': False, 'message': 'No jobs selected.'})
    
    updated = JobVacancy.objects.filter(
        id__in=job_ids,
        is_approved=False
    ).update(
        is_approved=True,
        approved_by=request.user,
        approved_at=timezone.now()
    )
    
    messages.success(request, f'{updated} job(s) approved successfully.')
    
    return JsonResponse({'success': True, 'count': updated})


@staff_member_required(login_url='accounts:login')
@require_POST
def bulk_delete_jobs(request):
    """
    Bulk delete multiple jobs.
    Access: Staff and Superusers
    """
    job_ids = request.POST.getlist('job_ids')
    
    if not job_ids:
        return JsonResponse({'success': False, 'message': 'No jobs selected.'})
    
    deleted, _ = JobVacancy.objects.filter(id__in=job_ids).delete()
    
    messages.success(request, f'{deleted} job(s) deleted successfully.')
    
    return JsonResponse({'success': True, 'count': deleted})



# ============================================
# SYSTEM HEALTH
# ============================================

@staff_member_required(login_url='accounts:login')
def system_health(request):
    """
    System health check and monitoring.
    Access: Staff and Superusers
    """
    from django.db import connection
    from django.core.cache import cache
    from apps.ingestion.models import IngestionJob
    
    # Database status
    db_status = 'OK' if connection.connection else 'ERROR'
    
    # Cache status
    try:
        cache.set('health_check', 'ok', 10)
        cache_status = 'OK' if cache.get('health_check') == 'ok' else 'ERROR'
    except:
        cache_status = 'ERROR'
    
    # Recent failed ingestion jobs
    failed_ingestions = IngestionJob.objects.filter(
        status='FAILED'
    ).order_by('-created_at')[:10]
    
    # Stale pending jobs (older than 1 hour)
    stale_threshold = timezone.now() - timedelta(hours=1)
    stale_ingestions = IngestionJob.objects.filter(
        status__in=['PENDING', 'PROCESSING'],
        created_at__lt=stale_threshold
    )
    
    # Expired jobs count
    expired_jobs = JobVacancy.objects.filter(
        expiry_date__lt=timezone.now().date(),
        is_approved=True
    ).count()
    
    context = {
        'db_status': db_status,
        'cache_status': cache_status,
        'failed_ingestions': failed_ingestions,
        'stale_ingestions': stale_ingestions,
        'stale_count': stale_ingestions.count(),
        'expired_jobs': expired_jobs,
        'django_version': __import__('django').get_version(),
    }
    
    return render(request, 'dashboard/system_health.html', context)