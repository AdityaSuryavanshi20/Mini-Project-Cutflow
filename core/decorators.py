from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*roles):
    """
    Decorator that restricts a view to users whose profile role is in `roles`,
    or who are admins (profile.is_admin or is_superuser). Redirects to the
    dashboard with an error message if the check fails.

    Usage:
        @role_required('salesman', 'admin')
        def my_view(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            # Superusers bypass all role checks regardless of profile state.
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if not hasattr(request.user, 'profile'):
                messages.error(request, 'No profile found. Contact an administrator.')
                return redirect('login')
            if request.user.profile.role not in roles and not request.user.profile.is_admin:
                messages.error(request, 'Access denied.')
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
