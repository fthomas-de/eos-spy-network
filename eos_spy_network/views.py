import time

from kombu.exceptions import OperationalError

from django.contrib import messages
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter

from . import __version__, contacts, contract_details, killmails, progress
from . import snapshot as snapshots
from .forms import SpyConfigurationForm
from .hostiles import save_sources, source_rows
from .markers import BLUE_KILLS, CONTACTS, KINDS, LABELS, corptools_installed, own_kill
from .models import KILL_NOTE_LENGTH, BlueKill, ContactSource, FindingReview, SpyConfiguration
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

# the sub-tabs of the settings page; the first opens unless another is asked for
TAB_ALLIANCE = "alliance"
TAB_SOURCES = "sources"
TAB_MARKERS = "markers"
TAB_KILLS = "kills"
SETTINGS_TABS = (TAB_ALLIANCE, TAB_SOURCES, TAB_MARKERS, TAB_KILLS)


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
    disabled = config.disabled_markers or ()
    reviews = {} if BLUE_KILLS in disabled else snapshots.kill_reviews(config.alliance.alliance_id)
    findings = {} if CONTACTS in disabled else snapshots.finding_reviews(config.alliance.alliance_id)
    return snapshots.Report(current, disabled, reviews, findings)


def open_mains() -> int:
    """Mains with a marker not switched off nor cleared, as the Corporation pages list them; the menu badge."""
    report = _report(SpyConfiguration.get_solo())
    return sum(len(tile.suspects) for tile in report.tiles) if report else 0


def _victim_mains(victim_ids) -> dict:
    """Victim character ID -> the ID of its account's main, for the audit link; a victim without an account is left out.

    Read at every view, not stored: an alt can change hands without a recalculation.
    """
    return dict(
        CharacterOwnership.objects.filter(
            character__character_id__in=victim_ids, user__profile__main_character__isnull=False
        ).values_list("character__character_id", "user__profile__main_character__character_id")
    )


def _kill_rows(config) -> list:
    """Every stored blue kill of the configured Alliance, one row per main and killmail, the latest first."""
    if not config.alliance:
        return []
    kills = list(
        BlueKill.objects.filter(alliance_id=config.alliance.alliance_id)
        .select_related("reviewed_by__profile__main_character")
        .order_by("-time", "killmail_id", "character_id")
    )
    character_ids = {kill.character_id for kill in kills}
    names = dict(
        EveCharacter.objects.filter(character_id__in=character_ids).values_list("character_id", "character_name")
    )
    victim_ids = {kill.victim_id for kill in kills if kill.victim_id}
    owners = dict(
        CharacterOwnership.objects.filter(character__character_id__in=character_ids | victim_ids).values_list(
            "character__character_id", "user_id"
        )
    )
    groups = {}
    # a copy made before own kills were left out
    for kill in (kill for kill in kills if not own_kill(owners, kill.character_id, kill.victim_id)):
        # a character nobody owns stands alone
        owner = owners.get(kill.character_id, ("character", kill.character_id))
        groups.setdefault((kill.killmail_id, owner), []).append(kill)
    mains = _victim_mains(victim_ids)
    rows = []
    for group in groups.values():
        row = group[0]
        row.named_characters = [
            (kill.character_id, names.get(kill.character_id) or str(kill.character_id)) for kill in group
        ]
        row.character = ", ".join(name for _character_id, name in row.named_characters)
        row.victim_main_id = mains.get(row.victim_id)
        # kill_note writes the group at once; a row reviewed alone before keeps the group open
        row.cleared = all(kill.cleared for kill in group)
        row.note = next((kill.note for kill in group if kill.note), "")
        latest = max((kill for kill in group if kill.reviewed_at), key=lambda kill: kill.reviewed_at, default=None)
        row.reviewed_at = latest.reviewed_at if latest else None
        row.reviewed_by = latest.reviewed_by if latest else None
        rows.append(row)
    return rows


@any_permission_required(VIEW_SUSPECTS)
@require_POST
def kill_note(request):
    """Stores the note and the cleared tick of one killmail for every character of the posted one's main."""
    config = SpyConfiguration.get_solo()
    try:
        character_id = int(request.POST.get("character_id", ""))
        killmail_id = int(request.POST.get("killmail_id", ""))
    except ValueError:
        return HttpResponseBadRequest("character_id and killmail_id must be numbers")
    text, cleared, refused = _posted_note(request)
    if refused:
        return refused
    # the user's rule: one tick per main and killmail, however many of its characters were on it
    owner = CharacterOwnership.objects.filter(character__character_id=character_id).values_list("user_id", flat=True)
    characters = CharacterOwnership.objects.filter(user_id__in=owner).values_list("character__character_id", flat=True)
    # only a kill of the configured Alliance: the pages show no other
    updated = BlueKill.objects.filter(
        alliance_id=config.alliance.alliance_id if config.alliance else None,
        killmail_id=killmail_id,
        character_id__in=[character_id, *characters],
    ).update(note=text, cleared=cleared, reviewed_at=timezone.now(), reviewed_by=request.user)
    if not updated:
        raise Http404
    return JsonResponse({"note": text, "cleared": cleared})


def _posted_note(request) -> tuple:
    """(note, cleared, None) as posted, or a refusal in the last place."""
    text = " ".join(request.POST.get("note", "").split())
    if len(text) > KILL_NOTE_LENGTH:
        return "", False, HttpResponseBadRequest("note too long")
    cleared = request.POST.get("cleared") == "1"
    # the user's rule: whoever clears a finding says why, or the next reader cannot tell what was checked
    if cleared and not text:
        return "", False, HttpResponseBadRequest("a cleared finding needs a note")
    return text, cleared, None


# the markers whose findings take a note and a tick here; blue kills have kill_note
REVIEWED_KINDS = (CONTACTS,)


@any_permission_required(VIEW_SUSPECTS)
@require_POST
def finding_note(request):
    """Stores the note and the cleared tick of one finding of a main."""
    config = SpyConfiguration.get_solo()
    if not config.alliance:
        raise Http404
    kind = request.POST.get("kind", "")
    key = request.POST.get("key", "")
    if kind not in REVIEWED_KINDS or not key or len(key) > FindingReview._meta.get_field("key").max_length:
        return HttpResponseBadRequest("unknown finding")
    try:
        main_id = int(request.POST.get("main_id", ""))
    except ValueError:
        return HttpResponseBadRequest("main_id must be a number")
    text, cleared, refused = _posted_note(request)
    if refused:
        return refused
    FindingReview.objects.update_or_create(
        alliance_id=config.alliance.alliance_id,
        kind=kind,
        main_id=main_id,
        key=key,
        defaults={"note": text, "cleared": cleared, "reviewed_at": timezone.now(), "reviewed_by": request.user},
    )
    return JsonResponse({"note": text, "cleared": cleared})


def _killmails_missing(config) -> str:
    """Why the blue kills cannot be found, for the notice above the marker pages; empty when they can."""
    if BLUE_KILLS in (config.disabled_markers or ()):
        return ""
    if not killmails.is_installed():
        return "not_installed"
    if not killmails.is_storing():
        return "not_storing"
    return ""


def _switched_off(config) -> list:
    """The labels of the markers the pages leave out, for the notice above them."""
    disabled = config.disabled_markers or ()
    return [LABELS[kind] for kind in KINDS if kind in disabled]


@any_permission_required(VIEW_SUSPECTS)
def corporations(request):
    started = time.perf_counter()
    config = SpyConfiguration.get_solo()
    report = _report(config)
    return _render(
        request,
        "eos_spy_network/corporations.html",
        {
            **_notices(config),
            "report": report,
            "tiles": report.tiles if report else [],
            "switched_off": _switched_off(config),
            "killmails_missing": _killmails_missing(config),
        },
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
    kill_rows = [
        row for suspect in tile.suspects if BLUE_KILLS in suspect.markers for row in suspect.markers[BLUE_KILLS].rows
    ]
    # a snapshot of 0.0.17 or older has no victim IDs until the next run
    mains = _victim_mains({row["victim_id"] for row in kill_rows if row.get("victim_id")})
    for row in kill_rows:
        row["victim_main_id"] = mains.get(row.get("victim_id"))
    return _render(
        request,
        "eos_spy_network/corporation.html",
        {
            **_notices(config),
            "report": report,
            "tile": tile,
            "note_length": KILL_NOTE_LENGTH,
            "switched_off": _switched_off(config),
            "killmails_missing": _killmails_missing(config),
        },
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


@all_permissions_required(VIEW_SUSPECTS, VIEW_EVIDENCE)
def contracts(request, character_id, counterpart_id):
    """The popup of a contract payment: the contracts of one own character with one counterpart, as HTML."""
    if not corptools_installed():
        raise Http404
    config = SpyConfiguration.get_solo()
    return render(
        request,
        "eos_spy_network/partials/contract-details.html",
        {
            "contracts": contract_details.details(
                character_id, counterpart_id, config.since(), config.ignored_ref_types or ()
            )
        },
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
    tab = request.GET.get("tab")

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
        # back to the tab whose Save button was pressed
        tab = request.POST.get("tab")
        target = reverse("eos_spy_network:settings")
        return redirect(f"{target}?tab={tab}" if tab in SETTINGS_TABS[1:] else target)

    if form.errors:
        # the tab with the error, or it hides behind another
        tab = TAB_MARKERS if set(form.errors) == {"markers"} else TAB_ALLIANCE
    return _render(
        request,
        "eos_spy_network/settings.html",
        {
            "form": form,
            "rows": rows,
            "kills": _kill_rows(config),
            "note_length": KILL_NOTE_LENGTH,
            "tab": tab if tab in SETTINGS_TABS else TAB_ALLIANCE,
        },
        NAV_SETTINGS,
    )
