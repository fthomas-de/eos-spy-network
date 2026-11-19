"""Who may use the app."""

from functools import wraps

from django.contrib.auth.decorators import login_required, user_passes_test

VIEW_SUSPECTS = "eos_spy_network.view_suspects"
MANAGE_SETTINGS = "eos_spy_network.manage_settings"
VIEW_OWN_CORPORATION = "eos_spy_network.view_own_corporation"

APP_PERMISSIONS = (VIEW_SUSPECTS, MANAGE_SETTINGS, VIEW_OWN_CORPORATION)


def has_app_access(user) -> bool:
    # any one of them opens the app; what a page shows is up to its own check
    return any(user.has_perm(perm) for perm in APP_PERMISSIONS)


def own_corporation_id(user) -> int | None:
    """The Corporation view_own_corporation opens: the one of the user's main; None without either."""
    main = user.profile.main_character if user.has_perm(VIEW_OWN_CORPORATION) else None
    return main.corporation_id if main else None


def sees_corporation(user, corporation_id) -> bool:
    # whoever sees a Corporation sees its evidence too: view_evidence is gone (user, 2026-11-19)
    return user.has_perm(VIEW_SUSPECTS) or corporation_id == own_corporation_id(user)


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
