from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from . import __version__, contacts
from .forms import SpyConfigurationForm
from .hostiles import save_sources, source_rows
from .markers import corporation_tiles, corptools_installed
from .models import ContactSource, SpyConfiguration
from .permissions import APP_PERMISSIONS, MANAGE_SETTINGS, VIEW_SUSPECTS, any_permission_required

# which page of the app this is, shown under its name
LOCATIONS = {
    "eos_spy_network/corporations.html": pgettext_lazy("eos-spy-network", "Corporations"),
    "eos_spy_network/corporation.html": _("Suspects"),
    "eos_spy_network/settings.html": _("Settings"),
}

NAV_CORPORATIONS = "corporations"
NAV_SETTINGS = "settings"


def _render(request, template, context=None, nav=None):
    return render(
        request,
        template,
        {
            "version": __version__,
            "location": LOCATIONS.get(template, ""),
            "nav": nav,
            "aa_contacts_installed": contacts.is_installed(),
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
    """What keeps the markers from being complete, for the notices above both pages."""
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
    }


@any_permission_required(VIEW_SUSPECTS)
def corporations(request):
    config = SpyConfiguration.get_solo()
    return _render(
        request,
        "eos_spy_network/corporations.html",
        {**_notices(config), "tiles": corporation_tiles(config)},
        NAV_CORPORATIONS,
    )


@any_permission_required(VIEW_SUSPECTS)
def corporation(request, corporation_id):
    config = SpyConfiguration.get_solo()
    # a Corporation outside the configured Alliance has no page
    tiles = corporation_tiles(config, corporation_id)
    if not tiles:
        raise Http404
    return _render(
        request,
        "eos_spy_network/corporation.html",
        {**_notices(config), "tile": tiles[0]},
        NAV_CORPORATIONS,
    )


@any_permission_required(MANAGE_SETTINGS)
def settings(request):
    config = SpyConfiguration.get_solo()
    form = SpyConfigurationForm(request.POST or None, instance=config)
    rows = source_rows(config)

    if request.method == "POST" and form.is_valid():
        form.save()
        # the ticks belong to the table the viewer saw: the Alliance before this save
        save_sources(rows, request.POST.getlist("source"))
        messages.success(request, _("Settings saved."))
        return redirect("eos_spy_network:settings")

    return _render(request, "eos_spy_network/settings.html", {"form": form, "rows": rows}, NAV_SETTINGS)
