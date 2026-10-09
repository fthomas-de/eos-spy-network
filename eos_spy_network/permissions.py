"""Who may use the app."""

from functools import wraps

from django.contrib.auth.decorators import login_required, user_passes_test

VIEW_SUSPECTS = "eos_spy_network.view_suspects"
VIEW_EVIDENCE = "eos_spy_network.view_evidence"
MANAGE_SETTINGS = "eos_spy_network.manage_settings"

APP_PERMISSIONS = (VIEW_SUSPECTS, VIEW_EVIDENCE, MANAGE_SETTINGS)


def has_app_access(user) -> bool:
    # any one of them opens the app; what a page shows is up to its own check
    return any(user.has_perm(perm) for perm in APP_PERMISSIONS)


def any_permission_required(*perms):
    """login_required plus at least one of ``perms``."""

    def decorator(view):
        @login_required
        @user_passes_test(lambda user: any(user.has_perm(perm) for perm in perms))
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def all_permissions_required(*perms):
    """login_required plus every one of ``perms``."""

    def decorator(view):
        @login_required
        @user_passes_test(lambda user: all(user.has_perm(perm) for perm in perms))
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
