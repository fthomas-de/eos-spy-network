"""Read API for other apps; a stable contract, change it only together with its users.

eos-auth-monitor shows the markers per character. It imports this module
inside an ``apps.is_installed("eos_spy_network")`` guard and checks the
permission ``eos_spy_network.view_suspects`` (whole Alliance) or
``eos_spy_network.view_own_corporation`` (the main's Corporation, through
``corporation_id``) itself; nothing here checks a permission.

Everything comes from the stored snapshot, as on this app's own pages: no
calculation, no query beyond the configuration, the one snapshot row and,
when the snapshot holds blue kills or other reviewable findings (Corporation
changes, contacts, mails, ISK, contracts), the reviewed ones (a query each).

- ``character_markers(*, corporation_id=None) -> dict[int, list[str]]``
- ``label(kind) -> str`` and ``description(kind) -> str``: the texts this app
  shows for a marker kind, translated lazily
- ``KINDS``: every marker kind, in the order the pages show them
"""

from .markers import BLUE_KILLS, CONTACTS, DESCRIPTIONS, KINDS, LABELS
from .models import SpyConfiguration
from .snapshot import CASES, current, finding_reviews, kill_reviews, reviewed_cases, reviewed_contacts, reviewed_kills

__all__ = ["KINDS", "character_markers", "description", "label"]


def character_markers(*, corporation_id: int | None = None) -> dict[int, list[str]]:
    """EVE character ID -> marker kinds found for it, in ``KINDS`` order.

    Only the account's own characters behind a finding appear, each under its
    own ID (not its main's). With ``corporation_id``, only what that
    Corporation's page shows: the mains of that Corporation with all their
    characters, an alt in another Corporation included, and the whole
    accounts of its visitors (an alt there, the main elsewhere) - what a CEO with
    ``view_own_corporation`` sees (the caller checks that permission, see
    ``permissions.sees_corporation``); empty for a Corporation without a page.
    Markers switched off in the settings are left out, as on this app's pages, and so are the cleared findings of every marker that has a tick. Empty without a snapshot, and when the
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
    # read once, and only when there is a marker to apply them to
    reviews = findings = None
    for corporation in snapshot.data["corporations"]:
        # the page's own lookup (Report.tile): the entry's id, not the suspects' corporation_id
        if corporation_id is not None and corporation["id"] != corporation_id:
            continue
        # the visitors' whole accounts too: that page shows them, and a main outside the Alliance is only there
        for suspect in [*corporation["suspects"], *corporation.get("visitors", [])]:
            for marker in suspect["markers"]:
                if marker["kind"] in disabled:
                    continue
                # a cleared finding is no longer a problem in eos-auth-monitor either
                if marker["kind"] == BLUE_KILLS:
                    if reviews is None:
                        reviews = kill_reviews(alliance_id)
                    marker = reviewed_kills(marker, reviews)
                # a marker without rows (a snapshot older than its reviews) has nothing to review: no query
                elif marker["kind"] in (CONTACTS, *CASES) and marker.get("rows"):
                    if findings is None:
                        findings = finding_reviews(alliance_id)
                    reviewed = reviewed_contacts if marker["kind"] == CONTACTS else reviewed_cases
                    marker = reviewed(marker, suspect["main_id"], findings)
                if marker is None:
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
