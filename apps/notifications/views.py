"""
Views for managing notifications and preferences.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.utils import timezone

from .models import Notification, NotificationPreference, JobAlert, NotificationDigest
from .forms import NotificationPreferenceForm, JobAlertForm


@login_required
def notification_list(request):
    """
    Display user's notifications.
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
    """
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_read()
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def mark_all_read(request):
    """
    Mark all notifications as read.
    """
    Notification.objects.filter(
        user=request.user,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())
    
    return JsonResponse({'success': True})


@login_required
def notification_preferences(request):
    """
    Manage notification preferences.
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


@login_required
def job_alerts(request):
    """
    Manage job alerts.
    """
    alerts = JobAlert.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'alerts': alerts,
    }
    
    return render(request, 'notifications/job_alerts.html', context)


@login_required
def create_job_alert(request):
    """
    Create a new job alert.
    """
    if request.method == 'POST':
        form = JobAlertForm(request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.user = request.user
            alert.save()
            messages.success(request, f'Job alert "{alert.name}" created successfully.')
            return redirect('notifications:job_alerts')
    else:
        # Pre-populate from search params
        initial = {}
        if 'q' in request.GET:
            initial['keywords'] = request.GET.get('q')
        if 'location' in request.GET:
            initial['location'] = request.GET.get('location')
        
        form = JobAlertForm(initial=initial)
    
    return render(request, 'notifications/create_alert.html', {'form': form})


@login_required
@require_POST
def toggle_alert(request, pk):
    """
    Toggle job alert active status.
    """
    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    alert.is_active = not alert.is_active
    alert.save(update_fields=['is_active'])
    
    return JsonResponse({
        'success': True,
        'is_active': alert.is_active
    })


@login_required
@require_POST
def delete_alert(request, pk):
    """
    Delete a job alert.
    """
    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    alert.delete()
    
    return JsonResponse({'success': True})


@login_required
def digest_detail(request, pk):
    """
    View a specific notification digest.
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


def get_unread_count(request):
    """
    AJAX endpoint for unread notification count.
    Used in navigation bar.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
    
    count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    return JsonResponse({'count': count})