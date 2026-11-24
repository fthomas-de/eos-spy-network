"""Whether a character was in the Alliance when something happened.

A payment, a contract, a mail or a kill counts for the checks only if its character was in a Corporation of
the Alliance at that time (user, 2026-11-23): what a character did before it joined, or after it left, says
nothing about the Alliance's members.

Two histories answer that. corptools holds the Corporations a character was in and since when. Auth knows
only a Corporation's Alliance of today, so the Corporation's own history comes from ESI's public alliance
history, kept in ``CorporationAlliances`` by the calculation task and refreshed once a day. Only the task asks
ESI, never a page view.

Where a history is missing the present stands in: a character corptools has no history of counts through its
current Corporation, a Corporation ESI could not be asked about counts if Auth has it in the Alliance now.
"""

from bisect import bisect_right
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from esi.openapi_clients import ESIClientProvider

from django.apps import apps
from django.utils import timezone

from allianceauth.eveonline import __esi_compatibility_date__
from allianceauth.eveonline.models import EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger

from . import __version__
from .models import CorporationAlliances

logger = get_extension_logger(__name__)

# Alliance Auth's own provider loads a fixed list of operations; this one is not on it
esi = ESIClientProvider(
    compatibility_date=__esi_compatibility_date__,
    ua_appname="eos-spy-network",
    ua_version=__version__,
    ua_url="https://github.com/fthomas-de/eos-spy-network",
    operations=["GetCorporationsCorporationIdAlliancehistory"],
)

# a Corporation joins or leaves an Alliance rarely; a day is as fresh as ESI's own cache of the list
STALE_AFTER = timedelta(days=1)
# the first run asks for every Corporation any character was ever in; the rest follows the next runs
# shortcut: a plain cap, no prioritising beyond "the Alliance's own first"; upgrade when a run is too slow
MAX_PER_RUN = 500
# ESI down: stop asking after this many failures in a row, every further call would only wait for its timeout
MAX_FAILURES = 5
# NPC Corporations are never in an Alliance
NPC_CORPORATIONS = range(1_000_000, 2_000_000)
BEGINNING = datetime.min.replace(tzinfo=UTC)


def _esi_alliance_history(corporation_id: int) -> list | None:
    """[[ISO start, Alliance ID or None], ...] oldest first; None when ESI could not be asked."""
    try:
        rows = esi.client.Corporation.GetCorporationsCorporationIdAlliancehistory(
            corporation_id=corporation_id
        ).results(use_etag=False, store_cache=False)
    except Exception as error:  # noqa: BLE001
        logger.warning("ESI alliance history of Corporation %s failed: %s", corporation_id, error)
        return None
    rows = sorted(rows, key=lambda row: (row.start_date, row.record_id))
    return [[row.start_date.isoformat(), getattr(row, "alliance_id", None) or None] for row in rows]


class Tenure:
    """Answers ``counts(character_id, when)`` from the two histories."""

    def __init__(self, alliance_id: int, corporations_now: set, characters: dict, alliances: dict):
        self.alliance_id = alliance_id
        # Corporations Auth has in the Alliance now: the fallback for a Corporation without a history
        self.corporations_now = corporations_now
        # character ID -> [(start, Corporation ID)], oldest first
        self.characters = characters
        # Corporation ID -> [(start, Alliance ID or None)], oldest first
        self.alliances = alliances

    def counts(self, character_id: int, when: datetime | None) -> bool:
        """The character was in a Corporation of the Alliance at ``when``; an undated item stays in."""
        if when is None:
            return True
        records = self.characters.get(character_id)
        if not records:
            return False
        found = bisect_right(records, when, key=lambda record: record[0]) - 1
        return found >= 0 and self._in_alliance(records[found][1], when)

    def _in_alliance(self, corporation_id: int, when: datetime) -> bool:
        history = self.alliances.get(corporation_id)
        if history is None:
            return corporation_id in self.corporations_now
        found = bisect_right(history, when, key=lambda record: record[0]) - 1
        return found >= 0 and history[found][1] == self.alliance_id


def load(config, characters: list, since: datetime | None = None) -> Tenure:
    """The Tenure of ``characters`` (``markers.Roster.characters``), asking ESI for the stale histories."""
    from .markers import character_audits

    alliance_id = config.alliance.alliance_id
    corporations_now = set(
        EveCorporationInfo.objects.filter(alliance=config.alliance).values_list("corporation_id", flat=True)
    )
    current = {character_id: corporation_id for _user_id, character_id, _name, corporation_id, _alliance in characters}

    records = defaultdict(list)
    if apps.is_installed("corptools"):
        from corptools.models import CorporationHistory

        audits = character_audits(list(current))
        for audit_id, corporation_id, start_date in CorporationHistory.objects.filter(
            character_id__in=list(audits)
        ).values_list("character_id", "corporation_id", "start_date"):
            records[audits[audit_id]].append((start_date, corporation_id))
    for character_id, corporation_id in current.items():
        # a character corptools has not read yet: its Corporation of today, from the beginning
        if character_id not in records:
            records[character_id] = [(BEGINNING, corporation_id)]
        records[character_id].sort()

    corporations = _needed(records, since)
    return Tenure(alliance_id, corporations_now, dict(records), _histories(corporations, corporations_now))


def _needed(records: dict, since: datetime | None) -> set[int]:
    """The Corporations whose membership period reaches into the time frame."""
    needed = set()
    for history in records.values():
        ends = [following[0] for following in history[1:]] + [None]
        for (_start, corporation_id), end in zip(history, ends):
            if corporation_id not in NPC_CORPORATIONS and (since is None or end is None or end >= since):
                needed.add(corporation_id)
    return needed


def _histories(corporations: set, corporations_now: set) -> dict:
    """Corporation ID -> [(start, Alliance ID or None)]; refreshes what is stale and ESI can still answer."""
    now = timezone.now()
    stored = {row.pk: row for row in CorporationAlliances.objects.filter(pk__in=corporations)}
    stale = sorted(
        (corporation_id for corporation_id in corporations if corporation_id not in stored or stored[corporation_id].fetched_at < now - STALE_AFTER),
        # the Alliance's own Corporations matter most; then the oldest entries
        key=lambda corporation_id: (
            corporation_id not in corporations_now,
            stored[corporation_id].fetched_at if corporation_id in stored else BEGINNING,
        ),
    )[:MAX_PER_RUN]
    failures = 0
    for corporation_id in stale:
        history = _esi_alliance_history(corporation_id)
        if history is None:
            failures += 1
            if failures >= MAX_FAILURES:
                logger.warning("ESI alliance history stopped after %d failures in a row", failures)
                break
            continue
        failures = 0
        stored[corporation_id], _created = CorporationAlliances.objects.update_or_create(
            pk=corporation_id, defaults={"history": history, "fetched_at": now}
        )
    return {
        corporation_id: [(datetime.fromisoformat(start), alliance) for start, alliance in row.history]
        for corporation_id, row in stored.items()
    }
