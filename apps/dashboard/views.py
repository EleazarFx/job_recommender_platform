"""
Admin dashboard views for managing jobs, users, and data ingestion.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin
from datetime import timedelta
import json

from apps.jobs.models import JobVacancy, JobCategory, JobReport
from apps.accounts.models import User
from apps.ingestion.models import DataSource, IngestionJob
from apps.ingestion.forms import DataSourceForm, CSVUploadForm
from apps.ingestion.tasks import process_csv_upload, fetch_api_data


class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to staff users only."""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def handle_no_permission(self):
        messages.error(self.request, 'You do not have permission to access this area.')
        return redirect('core:home')


@staff_member_required
def dashboard_home(request):
    """Main admin dashboard with statistics."""
    
    # Time periods for comparison
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Statistics
    context = {
        'total_users': User.objects.count(),
        'new_users_week': User.objects.filter(date_joined__date__gte=week_ago).count(),
        'total_jobs': JobVacancy.objects.filter(is_approved=True).count(),
        'pending_approvals': JobVacancy.objects.filter(is_approved=False).count(),
        'expired_jobs': JobVacancy.objects.filter(expiry_date__lt=today, is_approved=True).count(),
        'total_reports': JobReport.objects.filter(reviewed=False).count(),
        
        # Recent activity
        'recent_jobs': JobVacancy.objects.order_by('-date_posted')[:10],
        'recent_users': User.objects.order_by('-date_joined')[:10],
        'pending_reports': JobReport.objects.filter(reviewed=False).select_related('job', 'reported_by')[:5],
        
        # Charts data
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


@staff_member_required
def ingestion_dashboard(request):
    """Data ingestion management page."""
    
    # Get all data sources
    data_sources = DataSource.objects.all().order_by('-is_active', 'name')
    
    # Recent ingestion jobs
    recent_jobs = IngestionJob.objects.select_related('data_source', 'created_by').order_by('-created_at')[:20]
    
    context = {
        'data_sources': data_sources,
        'recent_jobs': recent_jobs,
        'csv_form': CSVUploadForm(),
        'source_form': DataSourceForm(),
    }
    
    return render(request, 'dashboard/ingestion.html', context)


@staff_member_required
@require_POST
def upload_csv(request):
    """Handle CSV file upload with column mapping."""
    form = CSVUploadForm(request.POST, request.FILES)
    
    if form.is_valid():
        # Create ingestion job
        ingestion_job = form.save(commit=False)
        ingestion_job.created_by = request.user
        ingestion_job.status = IngestionJob.Status.PENDING
        ingestion_job.save()
        
        # Get column mapping
        column_mapping = json.loads(form.cleaned_data['column_mapping'])
        
        # Start background task
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


@staff_member_required
def preview_csv_columns(request):
    """Preview CSV columns for mapping."""
    if request.method == 'POST' and request.FILES.get('csv_file'):
        import pandas as pd
        
        csv_file = request.FILES['csv_file']
        
        try:
            # Read first few rows to get columns
            df = pd.read_csv(csv_file, nrows=5)
            columns = df.columns.tolist()
            
            # Get sample data
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


class DataSourceCreateView(AdminRequiredMixin, CreateView):
    """Create new data source."""
    model = DataSource
    form_class = DataSourceForm
    template_name = 'dashboard/datasource_form.html'
    success_url = reverse_lazy('dashboard:ingestion')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Data source created successfully.')
        return super().form_valid(form)


class DataSourceUpdateView(AdminRequiredMixin, UpdateView):
    """Update data source."""
    model = DataSource
    form_class = DataSourceForm
    template_name = 'dashboard/datasource_form.html'
    success_url = reverse_lazy('dashboard:ingestion')
    
    def form_valid(self, form):
        messages.success(self.request, 'Data source updated successfully.')
        return super().form_valid(form)


@staff_member_required
@require_POST
def trigger_sync(request, pk):
    """Manually trigger sync for a data source."""
    data_source = get_object_or_404(DataSource, pk=pk)
    
    if data_source.source_type in ['API_JSON', 'API_XML']:
        fetch_api_data(data_source.id)
        messages.success(request, f'Sync triggered for {data_source.name}')
    else:
        messages.error(request, 'Manual sync only available for API sources')
    
    return redirect('dashboard:ingestion')


@staff_member_required
def job_approval_queue(request):
    """View for approving/rejecting pending jobs."""
    
    pending_jobs = JobVacancy.objects.filter(
        is_approved=False
    ).select_related('posted_by').order_by('-date_posted')
    
    # Pagination
    paginator = Paginator(pending_jobs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_pending': pending_jobs.count(),
    }
    
    return render(request, 'dashboard/job_approval.html', context)


@staff_member_required
@require_POST
def approve_job(request, pk):
    """Approve a pending job."""
    job = get_object_or_404(JobVacancy, pk=pk, is_approved=False)
    
    job.is_approved = True
    job.approved_by = request.user
    job.approved_at = timezone.now()
    job.save()
    
    messages.success(request, f'Job "{job.title}" has been approved.')
    
    return JsonResponse({'success': True})


@staff_member_required
@require_POST
def reject_job(request, pk):
    """Reject and delete a pending job."""
    job = get_object_or_404(JobVacancy, pk=pk, is_approved=False)
    
    title = job.title
    job.delete()
    
    messages.warning(request, f'Job "{title}" has been rejected and deleted.')
    
    return JsonResponse({'success': True})


@staff_member_required
def reports_dashboard(request):
    """View and manage job reports."""
    
    reports = JobReport.objects.select_related(
        'job', 'reported_by'
    ).order_by('-created_at')
    
    # Filter options
    filter_status = request.GET.get('status', 'pending')
    if filter_status == 'pending':
        reports = reports.filter(reviewed=False)
    elif filter_status == 'reviewed':
        reports = reports.filter(reviewed=True)
    
    # Pagination
    paginator = Paginator(reports, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'filter_status': filter_status,
        'total_reports': reports.count(),
    }
    
    return render(request, 'dashboard/reports.html', context)


@staff_member_required
@require_POST
def resolve_report(request, pk):
    """Mark a report as reviewed."""
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