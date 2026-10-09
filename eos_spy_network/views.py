import time

from kombu.exceptions import OperationalError

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from . import __version__, contacts, progress
from . import snapshot as snapshots
from .forms import SpyConfigurationForm
from .hostiles import save_sources, source_rows
from .markers import corptools_installed
from .models import ContactSource, SpyConfiguration
from .permissions import (
    APP_PERMISSIONS,
    MANAGE_SETTINGS,
    VIEW_EVIDENCE,
    VIEW_SUSPECTS,
    all_permissions_required,
    any_permission_required,
)
from .tasks import update_snapshot

# which page of the app this is, shown under its name
LOCATIONS = {
    "eos_spy_network/corporations.html": _("Markers"),
    "eos_spy_network/corporation.html": _("Suspects"),
    "eos_spy_network/network.html": _("Network"),
    "eos_spy_network/network_corporation.html": _("Network"),
    "eos_spy_network/settings.html": _("Settings"),
}

NAV_MARKERS = "markers"
NAV_NETWORK = "network"
NAV_SETTINGS = "settings"


def _render(request, template, context=None, nav=None, started=None):
    return render(
        request,
        template,
        {
            "version": __version__,
            "location": LOCATIONS.get(template, ""),
            "nav": nav,
            "aa_contacts_installed": contacts.is_installed(),
            # how long the view took to get its data, for the footer
            "page_ms": round((time.perf_counter() - started) * 1000) if started else None,
            **(context or {}),
        },
    )


@any_permission_required(*APP_PERMISSIONS)
def index(request):
    # the first page the viewer may open
    if not request.user.has_perm(VIEW_SUSPECTS) and request.user.has_perm(MANAGE_SETTINGS):
        return redirect("eos_spy_network:settings")
    return redirect("eos_spy_network:corporations")


def _notices(config) -> dict:
    """What keeps the markers from being complete, for the notices above the pages."""
    sources = list(ContactSource.objects.order_by("kind", "name"))
    tokens = contacts.token_states([(source.kind, source.entity_id) for source in sources])
    # without a token or before aa-contacts' first run they add no hostiles
    unread = [
        source
        for source in sources
        if (source.kind, source.entity_id) not in tokens
        or tokens[(source.kind, source.entity_id)].contacts_modified is None
    ]
    return {
        "config": config,
        "corptools_installed": corptools_installed(),
        "source_count": len(sources),
        "sources_without_contacts": unread,
        # a running recalculation shows its bar instead of the button
        "progress": progress.current(),
    }


def _report(config) -> snapshots.Report | None:
    current = snapshots.current()
    # after a change of the Alliance the stored result is of the old one until recalculated
    if current is None or not config.alliance or current.data.get("alliance_id") != config.alliance.alliance_id:
        return None
    return snapshots.Report(current)


@any_permission_required(VIEW_SUSPECTS)
def corporations(request):
    started = time.perf_counter()
    config = SpyConfiguration.get_solo()
    report = _report(config)
    return _render(
        request,
        "eos_spy_network/corporations.html",
        {**_notices(config), "report": report, "tiles": report.tiles if report else []},
        NAV_MARKERS,
        started,
    )


@any_permission_required(VIEW_SUSPECTS)
def corporation(request, corporation_id):
    started = time.perf_counter()
    config = SpyConfiguration.get_solo()
    report = _report(config)
    # a Corporation outside the configured Alliance has no page
    tile = report.tile(corporation_id) if report else None
    if tile is None:
        raise Http404
    return _render(
        request,
        "eos_spy_network/corporation.html",
        {**_notices(config), "report": report, "tile": tile},
        NAV_MARKERS,
        started,
    )


# the connections are counterparts of wallet entries: evidence, as on the marker pages
@all_permissions_required(VIEW_SUSPECTS, VIEW_EVIDENCE)
def network(request):
    started = time.perf_counter()
    config = SpyConfiguration.get_solo()
    report = _report(config)
    return _render(
        request,
        "eos_spy_network/network.html",
        {**_notices(config), "report": report, "tiles": report.network_tiles if report else []},
        NAV_NETWORK,
        started,
    )


@all_permissions_required(VIEW_SUSPECTS, VIEW_EVIDENCE)
def network_corporation(request, corporation_id):
    started = time.perf_counter()
    config = SpyConfiguration.get_solo()
    report = _report(config)
    tile = report.network_tile(corporation_id) if report else None
    if tile is None:
        raise Http404
    return _render(
        request,
        "eos_spy_network/network_corporation.html",
        {**_notices(config), "report": report, "tile": tile},
        NAV_NETWORK,
        started,
    )


def _start_rebuild() -> bool:
    """Queue the task; False when the broker cannot take it."""
    progress.queued()
    try:
        update_snapshot.delay()
    except OperationalError:
        # Redis or the broker is down; a 500 would hide what else the request did
        progress.finished()
        return False
    return True


@any_permission_required(VIEW_SUSPECTS)
@require_POST
def rebuild(request):
    if _start_rebuild():
        messages.info(request, _("The markers and connections are being recalculated."))
    else:
        messages.error(request, _("The recalculation could not be started: the task queue is not reachable."))
    # back to the page the button was on; only our own pages, never elsewhere
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        target = ""
    return redirect(target or "eos_spy_network:index")


@any_permission_required(VIEW_SUSPECTS)
def rebuild_progress(request):
    """The running step for progress.js; ``running`` false once the task is done."""
    state = progress.current()
    return JsonResponse({"running": state is not None, **(state or {})})


@any_permission_required(MANAGE_SETTINGS)
def settings(request):
    config = SpyConfiguration.get_solo()
    form = SpyConfigurationForm(request.POST or None, instance=config)
    rows = source_rows(config)

    if request.method == "POST" and form.is_valid():
        form.save()
        # the ticks belong to the table the viewer saw: the Alliance before this save
        save_sources(rows, request.POST.getlist("source"))
        if _start_rebuild():
            messages.success(request, _("Settings saved. The markers and connections are being recalculated."))
        else:
            messages.warning(
                request,
                _("Settings saved, but the task queue is not reachable: recalculate once it is back."),
            )
        return redirect("eos_spy_network:settings")

    return _render(request, "eos_spy_network/settings.html", {"form": form, "rows": rows}, NAV_SETTINGS)
