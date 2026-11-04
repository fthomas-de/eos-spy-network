"""Read API for other apps; a stable contract, change it only together with its users.

eos-auth-monitor shows the markers per character. It imports this module
inside an ``apps.is_installed("eos_spy_network")`` guard and checks the
permissions ``eos_spy_network.view_suspects`` and
``eos_spy_network.view_evidence`` itself; nothing here checks a permission.

Everything comes from the stored snapshot, as on this app's own pages: no
calculation, no query beyond the configuration and the one snapshot row.

- ``character_markers() -> dict[int, list[str]]``
- ``label(kind) -> str`` and ``description(kind) -> str``: the texts this app
  shows for a marker kind, translated lazily
- ``KINDS``: every marker kind, in the order the pages show them
"""

from .markers import DESCRIPTIONS, KINDS, LABELS
from .models import SpyConfiguration
from .snapshot import current

__all__ = ["KINDS", "character_markers", "description", "label"]


def character_markers() -> dict[int, list[str]]:
    """EVE character ID -> marker kinds found for it, in ``KINDS`` order.

    Only the account's own characters behind a finding appear, each under its
    own ID (not its main's). Markers switched off in the settings are left
    out, as on this app's pages. Empty without a snapshot, and when the
    stored snapshot is of another Alliance than the configured one: after a
    change of the Alliance it is stale until recalculated. A snapshot built
    before 0.0.10 names no characters and gives nothing until the next run.
    """
    # one query, with the Alliance's EVE ID joined: get_solo() and config.alliance would take two
    config = (
        SpyConfiguration.objects.filter(pk=SpyConfiguration.singleton_instance_id)
        .values_list("alliance__alliance_id", "disabled_markers")
        .first()
    )
    if config is None:
        return {}
    alliance_id, disabled = config[0], set(config[1] or ())
    snapshot = current()
    # without an Alliance there is no snapshot of it: None never matches a stored one
    if snapshot is None or snapshot.data.get("alliance_id") != alliance_id:
        return {}

    found = {}
    for corporation in snapshot.data["corporations"]:
        for suspect in corporation["suspects"]:
            for marker in suspect["markers"]:
                if marker["kind"] in disabled:
                    continue
                for character_id in marker.get("character_ids", []):
                    found.setdefault(character_id, set()).add(marker["kind"])
    return {character_id: [kind for kind in KINDS if kind in kinds] for character_id, kinds in found.items()}


def label(kind: str) -> str:
    """The marker's name as this app shows it, e.g. "Hostile membership"."""
    return LABELS[kind]


def description(kind: str) -> str:
    """The one-sentence explanation this app shows for the marker."""
    return DESCRIPTIONS[kind]
