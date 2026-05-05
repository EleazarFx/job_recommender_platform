"""
Job listing, search, and detail views with role-based access control.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, F
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.utils.text import slugify
import csv

from .models import JobVacancy, JobCategory, JobView, SavedJob, JobReport
from .forms import JobSearchForm, JobReportForm, JobPostForm
from apps.recommendations.models import JobMatchScore
from apps.accounts.decorators import employer_required, job_seeker_required


# ============================================
# PUBLIC VIEWS (Accessible to all)
# ============================================

def job_list(request):
    """
    Main job listing page with search and filters.
    Access: Everyone (Public)
    """
    # Initialize search form
    form = JobSearchForm(request.GET)
    
    # Start with all active jobs
    queryset = JobVacancy.objects.select_related(
        'category', 'posted_by'
    ).filter(
        is_approved=True,
        expiry_date__gte=timezone.now().date()
    )
    
    # Apply filters
    if form.is_valid():
        try:
            queryset = form.filter_queryset(queryset)
        except Exception:
            queryset = queryset.order_by('-date_posted')
    else:
        queryset = queryset.order_by('-date_posted')
    
    # For logged-in users, annotate with match scores (for display)
    if request.user.is_authenticated:
        queryset = queryset.annotate(
            user_match_score=F('user_matches__match_score')
        )
    
    # For job seekers (but not staff/admin), filter to show only relevant matches
    if request.user.is_authenticated and request.user.user_type == 'JOB_SEEKER' and not request.user.is_staff:
        queryset = queryset.filter(
            Q(user_matches__user=request.user) | Q(user_matches__isnull=True)
        )
    
    # Count total results before pagination
    total_results = queryset.count()
    
    # Pagination (20 items per page for low bandwidth)
    paginator = Paginator(queryset, 20)
    page = request.GET.get('page', 1)
    
    try:
        jobs = paginator.page(page)
    except PageNotAnInteger:
        jobs = paginator.page(1)
    except EmptyPage:
        jobs = paginator.page(paginator.num_pages)
    
    # Get categories with counts for sidebar
    categories = JobCategory.objects.filter(
        is_active=True
    ).annotate(
        active_job_count=Count(
            'jobs',
            filter=Q(
                jobs__is_approved=True,
                jobs__expiry_date__gte=timezone.now().date()
            )
        )
    ).filter(active_job_count__gt=0)
    
    # Build active filters summary
    active_filters = []
    if form.cleaned_data.get('q'):
        active_filters.append(f"Search: '{form.cleaned_data['q']}'")
    if form.cleaned_data.get('location'):
        active_filters.append(f"Location: {form.cleaned_data['location']}")
    if form.cleaned_data.get('category'):
        active_filters.append(f"Category: {form.cleaned_data['category'].name}")
    if form.cleaned_data.get('remote_only'):
        active_filters.append("Remote only")
    
    # Get saved job IDs for current user
    saved_job_ids = []
    if request.user.is_authenticated:
        saved_job_ids = list(SavedJob.objects.filter(
            user=request.user
        ).values_list('job_id', flat=True))
    
    context = {
        'jobs': jobs,
        'form': form,
        'categories': categories,
        'total_results': total_results,
        'active_filters': active_filters,
        'is_paginated': jobs.has_other_pages(),
        'page_range': jobs.paginator.page_range,
        'saved_job_ids': saved_job_ids,
        # Permission flags for template
        'can_post_jobs': request.user.is_authenticated and request.user.user_type in ['EMPLOYER', 'ADMIN'],
        'is_job_seeker': request.user.is_authenticated and request.user.user_type == 'JOB_SEEKER',
    }
    
    return render(request, 'jobs/list.html', context)


def job_detail(request, pk, slug=None):
    """
    Job detail page with full description and application options.
    Access: Everyone (Public) - Actions vary by role
    """
    job = get_object_or_404(
        JobVacancy.objects.select_related('category', 'posted_by'),
        pk=pk,
        is_approved=True
    )
    
    # Redirect to canonical URL with slug
    canonical_slug = slugify(job.title)
    if slug != canonical_slug:
        return redirect('jobs:detail_with_slug', pk=job.pk, slug=canonical_slug)
    
    # Record view
    if request.user.is_authenticated:
        JobView.objects.get_or_create(
            job=job,
            user=request.user,
            defaults={
                'ip_address': request.META.get('REMOTE_ADDR'),
                'session_key': request.session.session_key
            }
        )
    
    job.increment_view_count()
    
    # Permission checks
    is_saved = False
    has_applied = False
    match_score = None
    is_owner = False
    can_edit = False
    can_view_applicants = False
    can_apply = False
    
    if request.user.is_authenticated:
        # Check if user saved this job (Job Seekers only)
        if request.user.user_type == 'JOB_SEEKER':
            is_saved = SavedJob.objects.filter(
                user=request.user,
                job=job
            ).exists()
            can_apply = True
            
            # Check if already applied
            from apps.interactions.models import JobApplication
            has_applied = JobApplication.objects.filter(
                job=job,
                applicant=request.user
            ).exists()
        
        # Check ownership (Employer who posted or Staff/Admin)
        is_owner = (job.posted_by == request.user)
        can_edit = is_owner or request.user.is_staff
        can_view_applicants = is_owner or request.user.is_staff
        
        # Get match score (Job Seekers only)
        if request.user.user_type == 'JOB_SEEKER':
            try:
                match_score = JobMatchScore.objects.get(
                    user=request.user,
                    job=job
                )
            except JobMatchScore.DoesNotExist:
                pass
    
    # Get similar jobs
    similar_jobs = []
    if job.required_skills:
        first_skill = job.required_skills.split(',')[0].strip()
        similar_jobs = JobVacancy.objects.filter(
            is_approved=True,
            expiry_date__gte=timezone.now().date()
        ).exclude(
            id=job.id
        ).filter(
            Q(required_skills__icontains=first_skill) |
            Q(category=job.category)
        ).order_by('-date_posted')[:6]
    
    # Get company's other jobs
    company_jobs = JobVacancy.objects.filter(
        company_name=job.company_name,
        is_approved=True,
        expiry_date__gte=timezone.now().date()
    ).exclude(id=job.id).order_by('-date_posted')[:3]
    
    context = {
        'job': job,
        'is_saved': is_saved,
        'has_applied': has_applied,
        'match_score': match_score,
        'similar_jobs': similar_jobs,
        'company_jobs': company_jobs,
        'report_form': JobReportForm(),
        # Permission flags
        'is_owner': is_owner,
        'can_edit': can_edit,
        'can_apply': can_apply,
        'can_view_applicants': can_view_applicants,
        'can_report': request.user.is_authenticated and not is_owner,
        'is_job_seeker': request.user.is_authenticated and request.user.user_type == 'JOB_SEEKER',
        'is_employer': request.user.is_authenticated and request.user.user_type == 'EMPLOYER',
        'is_verified_employer': request.user.is_authenticated and request.user.is_verified_employer,
    }
    
    return render(request, 'jobs/detail.html', context)


def category_jobs(request, slug):
    """
    View jobs in a specific category.
    Access: Everyone (Public)
    """
    category = get_object_or_404(JobCategory, slug=slug, is_active=True)
    
    jobs = JobVacancy.objects.filter(
        category=category,
        is_approved=True,
        expiry_date__gte=timezone.now().date()
    ).select_related('posted_by').order_by('-date_posted')
    
    # Pagination
    paginator = Paginator(jobs, 20)
    page = request.GET.get('page', 1)
    
    try:
        jobs_page = paginator.page(page)
    except PageNotAnInteger:
        jobs_page = paginator.page(1)
    except EmptyPage:
        jobs_page = paginator.page(paginator.num_pages)
    
    context = {
        'category': category,
        'jobs': jobs_page,
        'total_jobs': jobs.count(),
    }
    
    return render(request, 'jobs/category_jobs.html', context)


# ============================================
# JOB SEEKER ONLY VIEWS
# ============================================

@job_seeker_required
def save_job(request, pk):
    """
    Save/bookmark a job for later.
    Access: Job Seekers ONLY
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
    
    job = get_object_or_404(JobVacancy, pk=pk, is_approved=True)
    
    saved, created = SavedJob.objects.get_or_create(
        user=request.user,
        job=job
    )
    
    if created:
        JobVacancy.objects.filter(pk=job.pk).update(save_count=F('save_count') + 1)
        message = f'"{job.title}" has been saved to your bookmarks.'
    else:
        saved.delete()
        JobVacancy.objects.filter(pk=job.pk).update(save_count=F('save_count') - 1)
        message = f'"{job.title}" has been removed from your bookmarks.'
    
    return JsonResponse({
        'success': True,
        'is_saved': created,
        'message': message
    })


@job_seeker_required
def saved_jobs(request):
    """
    View user's saved/bookmarked jobs.
    Access: Job Seekers ONLY
    """
    # Return JSON count for AJAX/count_only requests (used by nav badges)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('count_only'):
        count = SavedJob.objects.filter(user=request.user).count()
        return JsonResponse({'count': count})

    saved = SavedJob.objects.filter(
        user=request.user
    ).select_related('job', 'job__category').order_by('-saved_at')

    # Pagination
    paginator = Paginator(saved, 20)
    page = request.GET.get('page', 1)

    try:
        saved_jobs = paginator.page(page)
    except PageNotAnInteger:
        saved_jobs = paginator.page(1)
    except EmptyPage:
        saved_jobs = paginator.page(paginator.num_pages)

    context = {
        'saved_jobs': saved_jobs,
        'total_saved': saved.count(),
    }

    return render(request, 'jobs/saved_jobs.html', context)


@job_seeker_required
def apply_job(request, pk):
    """
    Track job application and redirect to external URL or show email.
    Access: Job Seekers ONLY
    """
    job = get_object_or_404(JobVacancy, pk=pk, is_approved=True)
    
    if job.is_expired():
        messages.error(request, 'This job has expired and is no longer accepting applications.')
        return redirect('jobs:detail', pk=pk)
    
    # Record application
    from apps.interactions.models import JobApplication
    application, created = JobApplication.objects.get_or_create(
        job=job,
        applicant=request.user,
        defaults={
            'status': 'APPLIED',
            'applied_at': timezone.now()
        }
    )
    
    if created:
        job.application_count = F('application_count') + 1
        job.save(update_fields=['application_count'])
        messages.success(request, f'You have successfully applied to "{job.title}"!')
    else:
        messages.info(request, f'You have already applied to this job on {application.applied_at.date()}.')
    
    # Redirect to external URL or show application details
    if job.application_url:
        return redirect(job.application_url)
    else:
        messages.info(
            request,
            f'Please send your application to: {job.application_email}'
        )
        return redirect('jobs:detail', pk=pk)


# ============================================
# EMPLOYER ONLY VIEWS
# ============================================

@employer_required
def post_job(request):
    """
    Allow employers to post jobs.
    Verified employers get auto-approval.
    Access: Employers ONLY
    """
    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.posted_by = request.user
            
            # Set trust score and approval based on verification status
            if request.user.is_verified_employer:
                job.source_type = JobVacancy.SourceType.VERIFIED_EMPLOYER
                job.trust_score = 85
                job.is_approved = True
                job.is_verified_company = True
                success_message = 'Your job has been posted successfully!'
            else:
                job.source_type = JobVacancy.SourceType.GENERAL_USER
                job.trust_score = 50
                job.is_approved = False
                success_message = 'Your job has been submitted for review. It will appear once approved.'
            
            job.save()
            messages.success(request, success_message)
            
            return redirect('jobs:my_jobs')
    else:
        form = JobPostForm()
    
    context = {
        'form': form,
        'is_verified': request.user.is_verified_employer,
    }
    
    return render(request, 'jobs/post_job.html', context)


@employer_required
def my_jobs(request):
    """
    View jobs posted by the current employer.
    Access: Employers ONLY
    """
    jobs = JobVacancy.objects.filter(
        posted_by=request.user
    ).order_by('-date_posted')
    
    # Statistics
    today = timezone.now().date()
    
    context = {
        'jobs': jobs,
        'active_jobs': jobs.filter(is_approved=True, expiry_date__gte=today).count(),
        'pending_jobs': jobs.filter(is_approved=False).count(),
        'expired_jobs': jobs.filter(expiry_date__lt=today).count(),
        'total_applications': sum(job.application_count for job in jobs),
        'is_verified': request.user.is_verified_employer,
    }
    
    return render(request, 'jobs/my_jobs.html', context)


@login_required
def view_applicants(request, pk):
    """
    View applicants for a specific job.
    Access: Job Owner OR Staff/Admin
    """
    job = get_object_or_404(JobVacancy, pk=pk)
    
    # Permission check: Must be job owner OR staff/admin
    if job.posted_by != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to view applicants for this job.')
        return redirect('jobs:detail', pk=pk)
    
    from apps.interactions.models import JobApplication
    applications = JobApplication.objects.filter(
        job=job
    ).select_related('applicant', 'applicant__profile').order_by('-applied_at')
    
    context = {
        'job': job,
        'applications': applications,
        'total_applications': applications.count(),
    }
    
    return render(request, 'jobs/applicants.html', context)


# ============================================
# JOB MANAGEMENT (Owner or Staff only)
# ============================================

@login_required
@require_POST
def delete_job(request, pk):
    """
    Delete a job.
    Access: Job Owner OR Staff/Admin
    """
    job = get_object_or_404(JobVacancy, pk=pk)
    
    # Permission check
    if job.posted_by != request.user and not request.user.is_staff:
        return JsonResponse({
            'success': False,
            'message': 'You do not have permission to delete this job.'
        })
    
    title = job.title
    job.delete()
    
    messages.success(request, f'Job "{title}" has been deleted.')
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def extend_job(request, pk):
    """
    Extend job expiry date by 30 days.
    Access: Job Owner OR Staff/Admin
    """
    job = get_object_or_404(JobVacancy, pk=pk)
    
    # Permission check
    if job.posted_by != request.user and not request.user.is_staff:
        return JsonResponse({
            'success': False,
            'message': 'You do not have permission to extend this job.'
        })
    
    job.expiry_date = timezone.now().date() + timezone.timedelta(days=30)
    job.save(update_fields=['expiry_date'])
    
    messages.success(request, f'Job expiry date extended to {job.expiry_date}')
    
    return JsonResponse({'success': True, 'new_expiry': job.expiry_date.isoformat()})


# ============================================
# REPORTING (All authenticated users)
# ============================================

@login_required
@require_POST
def report_job(request, pk):
    """
    Report a suspicious job posting.
    Access: All authenticated users (except job owner)
    """
    job = get_object_or_404(JobVacancy, pk=pk)
    
    # Don't allow reporting own jobs
    if job.posted_by == request.user:
        return JsonResponse({
            'success': False,
            'message': 'You cannot report your own job posting.'
        })
    
    form = JobReportForm(request.POST)
    if form.is_valid():
        # Check if user already reported
        existing = JobReport.objects.filter(
            job=job,
            reported_by=request.user
        ).first()
        
        if existing:
            return JsonResponse({
                'success': False,
                'message': 'You have already reported this job.'
            })
        
        # Create report
        JobReport.objects.create(
            job=job,
            reported_by=request.user,
            reason=form.cleaned_data['reason'],
            details=form.cleaned_data['details']
        )
        
        # Update job report count
        job.report_count = F('report_count') + 1
        job.save(update_fields=['report_count'])
        
        return JsonResponse({
            'success': True,
            'message': 'Thank you for reporting this job. We will review it shortly.'
        })
    
    return JsonResponse({
        'success': False,
        'errors': form.errors
    })


# ============================================
# EXPORT (Staff only)
# ============================================

def export_jobs_csv(request):
    """
    Export filtered jobs as CSV.
    Access: Staff/Admin ONLY
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponse('Unauthorized', status=401)
    
    # Apply same filters as search
    form = JobSearchForm(request.GET)
    queryset = JobVacancy.objects.filter(is_approved=True)
    
    if form.is_valid():
        queryset = form.filter_queryset(queryset)
    
    # Limit to prevent abuse
    queryset = queryset[:1000]
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jobs_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Title', 'Company', 'Location', 'Job Type', 
        'Experience Level', 'Skills Required', 'Date Posted', 'Expiry Date',
        'Applications', 'Views', 'Trust Score'
    ])
    
    for job in queryset:
        writer.writerow([
            job.title,
            job.company_name,
            job.location_display,
            job.get_job_type_display(),
            job.get_experience_level_display(),
            job.required_skills,
            job.date_posted.date(),
            job.expiry_date,
            job.application_count,
            job.view_count,
            job.trust_score
        ])
    
    return response