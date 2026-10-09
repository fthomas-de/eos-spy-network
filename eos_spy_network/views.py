from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from . import __version__, contacts
from .forms import SpyConfigurationForm
from .hostiles import hostile_entities, save_sources, source_rows
from .models import ContactSource, SpyConfiguration
from .permissions import APP_PERMISSIONS, MANAGE_SETTINGS, VIEW_SUSPECTS, any_permission_required

# which page of the app this is, shown under its name
LOCATIONS = {
    "eos_spy_network/hostiles.html": _("Hostile list"),
    "eos_spy_network/settings.html": _("Settings"),
}

NAV_HOSTILES = "hostiles"
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
    return redirect("eos_spy_network:hostiles")


@any_permission_required(VIEW_SUSPECTS)
def hostiles(request):
    config = SpyConfiguration.get_solo()
    sources = list(ContactSource.objects.order_by("kind", "name"))
    tokens = contacts.token_states([(source.kind, source.entity_id) for source in sources])
    # without a token or before aa-contacts' first run they add nothing to the list
    unread = [
        source
        for source in sources
        if (source.kind, source.entity_id) not in tokens
        or tokens[(source.kind, source.entity_id)].contacts_modified is None
    ]
    return _render(
        request,
        "eos_spy_network/hostiles.html",
        {
            "config": config,
            "hostiles": hostile_entities(config),
            "source_count": len(sources),
            "sources_without_contacts": unread,
        },
        NAV_HOSTILES,
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
