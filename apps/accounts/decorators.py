"""
Custom decorators for role-based access control.
"""
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def job_seeker_required(view_func):
    """
    Restrict access to job seekers only.
    Staff/superusers bypass this restriction to allow system management.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)
            return redirect_to_login(request.get_full_path(), login_url=reverse('accounts:login'))

        # Allow job seekers, admins, and staff
        if request.user.user_type == 'JOB_SEEKER' or request.user.is_staff or request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Job seeker access required.'}, status=403)

        messages.error(request, "This area is for job seekers only.")
        return redirect('core:home')
    return wrapper


def employer_required(view_func):
    """
    Restrict access to employers (verified or not).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)
            return redirect_to_login(request.get_full_path(), login_url=reverse('accounts:login'))

        if request.user.user_type in ['EMPLOYER', 'ADMIN']:
            return view_func(request, *args, **kwargs)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Employer access required.'}, status=403)

        messages.error(request, "This area is for employers only.")
        return redirect('core:home')
    return wrapper


def verified_employer_required(view_func):
    """
    Restrict access to verified employers only.
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.user_type == 'EMPLOYER' and request.user.is_verified_employer:
            return view_func(request, *args, **kwargs)
        if request.user.user_type == 'ADMIN':
            return view_func(request, *args, **kwargs)
        
        messages.error(request, "This feature requires a verified employer account.")
        return redirect('core:home')
    return wrapper


def staff_required(view_func):
    """
    Restrict access to staff members only.
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        messages.error(request, "Staff access required.")
        raise PermissionDenied("Staff access required.")
    return wrapper


def admin_required(view_func):
    """
    Restrict access to superusers only.
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        messages.error(request, "Administrator access required.")
        raise PermissionDenied("Administrator access required.")
    return wrapper


def profile_owner_required(model_class=None, pk_url_kwarg='pk', owner_field='user'):
    """
    Decorator to ensure user owns the object they're trying to access.
    
    Usage:
        @profile_owner_required(JobVacancy, 'job_id', 'posted_by')
        def edit_job(request, job_id):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            pk = kwargs.get(pk_url_kwarg)
            
            if not pk:
                raise ValueError(f"URL keyword argument '{pk_url_kwarg}' not found.")
            
            try:
                obj = model_class.objects.get(pk=pk)
            except model_class.DoesNotExist:
                messages.error(request, "Object not found.")
                return redirect('core:home')
            
            # Check ownership
            owner = getattr(obj, owner_field)
            
            # Allow if user owns object OR is staff/admin
            if owner == request.user or request.user.is_staff:
                return view_func(request, *args, **kwargs)
            
            messages.error(request, "You don't have permission to access this.")
            return redirect('core:home')
        
        return wrapper
    return decorator