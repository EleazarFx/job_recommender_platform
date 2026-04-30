"""
Views for managing notifications and preferences.
With role-based access control and API endpoints.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta

from .models import Notification, NotificationPreference, JobAlert, NotificationDigest
from .forms import NotificationPreferenceForm, JobAlertForm
from apps.accounts.decorators import job_seeker_required


# ============================================
# NOTIFICATION LIST & MANAGEMENT
# ============================================

@login_required
def notification_list(request):
    """
    Display user's notifications.
    Access: All authenticated users
    """
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # Mark unread count
    unread_count = notifications.filter(is_read=False).count()
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page', 1)
    notifications_page = paginator.get_page(page)
    
    context = {
        'notifications': notifications_page,
        'unread_count': unread_count,
    }
    
    return render(request, 'notifications/list.html', context)


@login_required
@require_POST
def mark_as_read(request, pk):
    """
    Mark a single notification as read.
    Access: Notification owner only
    """
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_read()
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def mark_all_read(request):
    """
    Mark all notifications as read.
    Access: All authenticated users
    """
    Notification.objects.filter(
        user=request.user,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())
    
    return JsonResponse({'success': True})


# ============================================
# NOTIFICATION PREFERENCES
# ============================================

@login_required
def notification_preferences(request):
    """
    Manage notification preferences.
    Access: All authenticated users
    """
    # Get or create preferences
    prefs, created = NotificationPreference.objects.get_or_create(
        user=request.user
    )
    
    if request.method == 'POST':
        form = NotificationPreferenceForm(request.POST, instance=prefs)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notification preferences updated successfully.')
            return redirect('notifications:preferences')
    else:
        form = NotificationPreferenceForm(instance=prefs)
    
    context = {
        'form': form,
        'preferences': prefs,
    }
    
    return render(request, 'notifications/preferences.html', context)


# ============================================
# JOB ALERTS (Job Seekers Only)
# ============================================

@job_seeker_required
def job_alerts(request):
    """
    Manage job alerts.
    Access: Job Seekers ONLY
    """
    alerts = JobAlert.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'alerts': alerts,
        'total_alerts': alerts.count(),
        'active_alerts': alerts.filter(is_active=True).count(),
    }
    
    return render(request, 'notifications/job_alerts.html', context)


@job_seeker_required
def create_job_alert(request):
    """
    Create a new job alert.
    Access: Job Seekers ONLY
    """
    if request.method == 'POST':
        form = JobAlertForm(request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.user = request.user
            alert.save()
            messages.success(request, f'Job alert "{alert.name}" created successfully!')
            return redirect('notifications:job_alerts')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Pre-populate from search params
        initial = {}
        if 'q' in request.GET:
            initial['keywords'] = request.GET.get('q')
        if 'location' in request.GET:
            initial['location'] = request.GET.get('location')
        if 'job_type' in request.GET:
            initial['job_types'] = request.GET.getlist('job_type')
        
        form = JobAlertForm(initial=initial)
    
    return render(request, 'notifications/create_alert.html', {'form': form})


@job_seeker_required
@require_POST
def toggle_alert(request, pk):
    """
    Toggle job alert active status.
    Access: Alert owner only
    """
    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    alert.is_active = not alert.is_active
    alert.save(update_fields=['is_active'])
    
    return JsonResponse({
        'success': True,
        'is_active': alert.is_active,
        'message': f'Alert {"activated" if alert.is_active else "paused"} successfully.'
    })


@job_seeker_required
@require_POST
def delete_alert(request, pk):
    """
    Delete a job alert.
    Access: Alert owner only
    """
    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    name = alert.name
    alert.delete()
    
    messages.success(request, f'Job alert "{name}" deleted.')
    return JsonResponse({'success': True})


# ============================================
# NOTIFICATION DIGESTS
# ============================================

@login_required
def digest_detail(request, pk):
    """
    View a specific notification digest.
    Access: Digest owner only
    """
    digest = get_object_or_404(
        NotificationDigest.objects.prefetch_related('notifications__job'),
        pk=pk,
        user=request.user
    )
    
    if not digest.is_read:
        digest.is_read = True
        digest.save(update_fields=['is_read'])
    
    context = {
        'digest': digest,
        'notifications': digest.notifications.all(),
    }
    
    return render(request, 'notifications/digest_detail.html', context)


# ============================================
# API ENDPOINTS (For AJAX/Navigation)
# ============================================

def get_unread_count(request):
    """
    AJAX endpoint for unread notification count.
    Used in navigation bar badge.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
    
    count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    return JsonResponse({'count': count})


def recent_notifications_api(request):
    """
    API endpoint for recent notifications dropdown.
    Returns last 5 notifications for the nav dropdown.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'notifications': []})
    
    notifications = Notification.objects.filter(
        user=request.user
    ).select_related('job').order_by('-created_at')[:5]
    
    data = {
        'notifications': []
    }
    
    for n in notifications:
        # Determine icon and color based on notification type
        icon_map = {
            'JOB_MATCH': 'robot',
            'JOB_ALERT': 'bell',
            'APPLICATION_UPDATE': 'file-alt',
            'JOB_EXPIRING': 'hourglass-half',
            'SYSTEM': 'info-circle',
        }
        color_map = {
            'JOB_MATCH': 'primary',
            'JOB_ALERT': 'success',
            'APPLICATION_UPDATE': 'info',
            'JOB_EXPIRING': 'warning',
            'SYSTEM': 'secondary',
        }
        
        # Build URL based on notification type
        if n.job:
            url = f'/jobs/{n.job.id}/'
        elif n.job_alert:
            url = '/notifications/alerts/'
        else:
            url = '/notifications/'
        
        data['notifications'].append({
            'id': n.id,
            'title': n.title,
            'message': n.message[:100] + ('...' if len(n.message) > 100 else ''),
            'url': url,
            'is_read': n.is_read,
            'icon': icon_map.get(n.type, 'bell'),
            'color': color_map.get(n.type, 'primary'),
            'time_ago': time_since(n.created_at),
        })
    
    return JsonResponse(data)


def saved_jobs_count_api(request):
    """
    API endpoint for saved jobs count (JobSeeker-only).
    Used in navigation bar badge.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
    
    # Only JobSeekers save jobs
    if request.user.user_type != 'JOB_SEEKER':
        return JsonResponse({'count': 0})
    
    from apps.jobs.models import SavedJob
    count = SavedJob.objects.filter(user=request.user).count()
    
    return JsonResponse({'count': count})


def job_alerts_api(request):
    """
    API endpoint for user's job alerts (JobSeeker-only).
    Used in create alert sidebar.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'alerts': []})
    
    # Only JobSeekers have job alerts
    if request.user.user_type != 'JOB_SEEKER':
        return JsonResponse({'alerts': []})
    
    alerts = JobAlert.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    data = {
        'alerts': [
            {
                'name': a.name,
                'keywords': a.keywords or 'All keywords',
                'location': a.location or 'All locations',
                'frequency_display': a.get_frequency_display(),
                'is_active': a.is_active,
            }
            for a in alerts
        ]
    }
    
    return JsonResponse(data)


# ============================================
# HELPER FUNCTIONS
# ============================================

def time_since(dt):
    """
    Return a human-readable time difference string.
    """
    now = timezone.now()
    diff = now - dt
    
    if diff < timedelta(minutes=1):
        return 'Just now'
    elif diff < timedelta(hours=1):
        minutes = int(diff.seconds / 60)
        return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    elif diff < timedelta(days=1):
        hours = int(diff.seconds / 3600)
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    elif diff < timedelta(days=7):
        days = diff.days
        return f'{days} day{"s" if days != 1 else ""} ago'
    elif diff < timedelta(days=30):
        weeks = int(diff.days / 7)
        return f'{weeks} week{"s" if weeks != 1 else ""} ago'
    else:
        return dt.strftime('%b %d, %Y')