"""How far the running recalculation is, for the progress bar on the pages.

The task writes its current step into the cache and the pages poll it. The
cache, not the database: the entry only matters while the task runs, and it
expires - a worker that dies mid-run must not leave a bar behind for good.
"""

from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

KEY = "eos_spy_network:progress"
QUEUED = "queued"
# a queued run the worker never picks up (worker down) gives up the bar sooner
QUEUED_TIMEOUT = 10 * 60
RUNNING_TIMEOUT = 60 * 60

STEPS = {
    QUEUED: _("Waiting for the task queue"),
    "hostiles": _("Reading the hostile contacts"),
    "membership": _("Checking memberships"),
    "history": _("Checking Corporation histories"),
    "contacts": _("Checking contacts"),
    "mails": _("Checking mails"),
    "wallet": _("Checking wallet journals"),
    "contracts": _("Checking contracts"),
    "connections": _("Finding connections outside the Alliance"),
    "affiliations": _("Looking up Corporations and Alliances"),
    "saving": _("Saving the result"),
}
ORDER = list(STEPS)


def queued() -> None:
    """Show the bar at once after the click; a run already going keeps its own state."""
    cache.add(KEY, {"step": QUEUED}, QUEUED_TIMEOUT)


def step(name: str) -> None:
    cache.set(KEY, {"step": name}, RUNNING_TIMEOUT)


def finished() -> None:
    cache.delete(KEY)


def current() -> dict | None:
    """The running step with its label and percent; None when nothing runs."""
    state = cache.get(KEY)
    if not state or state.get("step") not in STEPS:
        return None
    name = state["step"]
    return {
        "step": name,
        "label": str(STEPS[name]),
        # the step that runs counts as begun, not done
        "percent": round(100 * ORDER.index(name) / len(ORDER)),
    }
