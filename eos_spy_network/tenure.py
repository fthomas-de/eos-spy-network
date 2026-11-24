"""Whether a character was in the Alliance when something happened.

A payment, a contract, a mail or a kill counts for the checks only if its character was in a Corporation of
the Alliance at that time (user, 2026-11-23): what a character did before it joined, or after it left, says
nothing about the Alliance's members.

Two histories answer that. corptools holds the Corporations a character was in and since when. Auth knows
only a Corporation's Alliance of today, so the Corporation's own history comes from ESI's public alliance
history, kept in ``CorporationAlliances`` by the calculation task and refreshed once a day, or less often the
longer the history has stood (``MAX_STALE``). Only the task asks ESI, never a page view.

Where a history is missing the present stands in: a character corptools has no history of counts through its
current Corporation, a Corporation ESI could not be asked about counts if Auth has it in the Alliance now.

The same holds for the other side (user, 2026-11-24): a counterpart that was in the Alliance at the time is no
counterpart, one that joined later is. Its Corporations come from corptools where it has an audit, else from ESI's
public corporation history, kept in ``CharacterCorporations``.
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
from .models import CharacterCorporations, CorporationAlliances

logger = get_extension_logger(__name__)

# Alliance Auth's own provider loads a fixed list of operations; this one is not on it
esi = ESIClientProvider(
    compatibility_date=__esi_compatibility_date__,
    ua_appname="eos-spy-network",
    ua_version=__version__,
    ua_url="https://github.com/fthomas-de/eos-spy-network",
    operations=["GetCorporationsCorporationIdAlliancehistory", "GetCharactersCharacterIdCorporationhistory"],
)

# a Corporation joins or leaves an Alliance rarely; a day is as fresh as ESI's own cache of the list
STALE_AFTER = timedelta(days=1)
# only the last entry of a history can still change, so one that has stood for long is asked less often: a
# thirtieth of the time since its last change, between STALE_AFTER and this. ESI's "nothing here" (a closed
# Corporation, a deleted character, a Corporation never in an Alliance) waits this long too
# shortcut: a plain cap; a Corporation that joins a hostile Alliance is seen up to this many days late, lower it if that hurts
MAX_STALE = timedelta(days=7)
# the first run asks for every Corporation any character was ever in; the rest follows the next runs
# shortcut: a plain cap, no prioritising beyond "the Alliance's own first"; upgrade when a run is too slow
MAX_PER_RUN = 500
# ESI down: stop asking after this many failures in a row, every further call would only wait for its timeout
MAX_FAILURES = 5
# NPC Corporations are never in an Alliance
NPC_CORPORATIONS = range(1_000_000, 2_000_000)
BEGINNING = datetime.min.replace(tzinfo=UTC)


def _not_found(error: Exception) -> bool:
    """ESI does not know the ID (closed Corporation, deleted character): an answer, not an outage."""
    return getattr(error, "status_code", None) == 404


def _esi_alliance_history(corporation_id: int) -> list | None:
    """[[ISO start, Alliance ID or None], ...] oldest first; None when ESI could not be asked."""
    try:
        rows = esi.client.Corporation.GetCorporationsCorporationIdAlliancehistory(
            corporation_id=corporation_id
        ).results(use_etag=False, store_cache=False)
    except Exception as error:  # noqa: BLE001
        if _not_found(error):
            return []
        logger.warning("ESI alliance history of Corporation %s failed: %s", corporation_id, error)
        return None
    rows = sorted(rows, key=lambda row: (row.start_date, row.record_id))
    return [[row.start_date.isoformat(), getattr(row, "alliance_id", None) or None] for row in rows]


def _esi_corporation_history(character_id: int) -> list | None:
    """[[ISO start, Corporation ID], ...] oldest first; None when ESI could not be asked."""
    try:
        rows = esi.client.Character.GetCharactersCharacterIdCorporationhistory(character_id=character_id).results(
            use_etag=False, store_cache=False
        )
    except Exception as error:  # noqa: BLE001
        if _not_found(error):
            return []
        logger.warning("ESI corporation history of character %s failed: %s", character_id, error)
        return None
    rows = sorted(rows, key=lambda row: (row.start_date, row.record_id))
    return [[row.start_date.isoformat(), row.corporation_id] for row in rows]


class Tenure:
    """Answers ``counts(character_id, when)`` from the two histories."""

    def __init__(self, alliance_id: int, corporations_now: set, characters: dict, alliances: dict, since=None):
        self.alliance_id = alliance_id
        self.since = since
        # counterparts ``prepare`` has looked up already, found or not
        self.prepared = set()
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

    def was_ours(self, eve_id: int, when: datetime | None) -> bool:
        """The character, Corporation or Alliance was ours at ``when`` (undated: today); ``prepare`` it first."""
        when = when or timezone.now()
        if eve_id == self.alliance_id:
            return True
        if eve_id in self.characters:
            return self.counts(eve_id, when)
        return (eve_id in self.alliances or eve_id in self.corporations_now) and self._in_alliance(eve_id, when)

    def prepare(self, ids, entities: dict | None = None) -> None:
        """Read the histories of the counterparts ``ids``; ``entities`` is ``affiliations.resolve``'s answer if at hand."""
        from .affiliations import resolve
        from .markers import character_audits

        ids = {eve_id for eve_id in ids if eve_id and eve_id not in self.prepared and eve_id not in self.characters}
        if not ids:
            return
        self.prepared |= ids
        entities = entities or {}
        missing = ids - entities.keys()
        found = {**entities, **(resolve(missing) if missing else {})}
        found = {eve_id: found[eve_id] for eve_id in ids if eve_id in found}
        for entity in found.values():
            # where no history answers, today's Alliance stands in - ESI's too, for a Corporation Auth does not know
            group_id = entity.id if entity.category == "corporation" else entity.corporation_id
            if group_id and entity.alliance_id == self.alliance_id:
                self.corporations_now.add(group_id)

        characters = [eve_id for eve_id, entity in found.items() if entity.category == "character"]
        records = defaultdict(list)
        if apps.is_installed("corptools"):
            from corptools.models import CorporationHistory

            audits = character_audits(characters)
            for audit_id, corporation_id, start_date in CorporationHistory.objects.filter(
                character_id__in=list(audits)
            ).values_list("character_id", "corporation_id", "start_date"):
                records[audits[audit_id]].append((start_date, corporation_id))
        unread = {character_id for character_id in characters if character_id not in records}
        # a counterpart in one of our Corporations is the one whose leaving matters: asked daily
        records.update(
            _refresh(CharacterCorporations, unread, _esi_corporation_history, daily=self.corporations_now.__contains__)
        )
        for character_id in characters:
            corporation_id = found[character_id].corporation_id
            history = records.get(character_id) or ([(BEGINNING, corporation_id)] if corporation_id else [])
            if history:
                self.characters[character_id] = sorted(history)

        known = {character_id: self.characters[character_id] for character_id in characters if character_id in self.characters}
        corporations = _needed(known, self.since) | {
            eve_id for eve_id, entity in found.items() if entity.category == "corporation" and eve_id not in NPC_CORPORATIONS
        }
        self.alliances.update(_histories(corporations - self.alliances.keys(), self.corporations_now, self.alliance_id))

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
    histories = _histories(corporations, corporations_now, alliance_id)
    return Tenure(alliance_id, corporations_now, dict(records), histories, since)


def _needed(records: dict, since: datetime | None) -> set[int]:
    """The Corporations whose membership period reaches into the time frame."""
    needed = set()
    for history in records.values():
        ends = [following[0] for following in history[1:]] + [None]
        for (_start, corporation_id), end in zip(history, ends):
            if corporation_id not in NPC_CORPORATIONS and (since is None or end is None or end >= since):
                needed.add(corporation_id)
    return needed


def _histories(corporations: set, corporations_now: set, alliance_id: int | None = None) -> dict:
    """Corporation ID -> [(start, Alliance ID or None)]; the Alliance's own Corporations matter most."""
    return _refresh(
        CorporationAlliances,
        corporations,
        _esi_alliance_history,
        corporations_now,
        lambda alliance: alliance is not None and alliance == alliance_id,
    )


def current_alliances(corporations) -> dict:
    """Corporation ID -> Alliance ID of today, from the stored history (asked from ESI when stale); None when it has none."""
    corporations = {eve_id for eve_id in corporations if eve_id not in NPC_CORPORATIONS}
    histories = _histories(corporations, frozenset()) if corporations else {}
    return {eve_id: histories[eve_id][-1][1] if eve_id in histories else None for eve_id in corporations}


def _stale(row, now, daily: bool) -> bool:
    """The stored history is older than it may be: ``daily`` ones a day, the rest by the age of their last entry."""
    if daily:
        limit = STALE_AFTER
    elif not row.history:
        limit = MAX_STALE
    else:
        limit = min(max((row.fetched_at - datetime.fromisoformat(row.history[-1][0])) / 30, STALE_AFTER), MAX_STALE)
    return row.fetched_at < now - limit


def _refresh(model, ids: set, fetch, first=frozenset(), daily=lambda value: False) -> dict:
    """ID -> [(start, value)] of ``model``; refreshes what is stale and ESI can still answer, ``first`` first.

    ``first`` and a row whose last value ``daily`` accepts are asked daily however long they have stood: a
    Corporation of ours that left, or one that joined, must show at once. Rows ESI knows nothing of are kept (an
    empty history) so they are not asked every run, but left out of the answer.
    """
    now = timezone.now()
    stored = {row.pk: row for row in model.objects.filter(pk__in=ids)}

    def wanted(eve_id) -> bool:
        row = stored.get(eve_id)
        return row is None or _stale(row, now, eve_id in first or bool(row.history and daily(row.history[-1][1])))

    stale = sorted(
        filter(wanted, ids),
        # then the oldest entries
        key=lambda eve_id: (eve_id not in first, stored[eve_id].fetched_at if eve_id in stored else BEGINNING),
    )[:MAX_PER_RUN]
    failures = 0
    for eve_id in stale:
        history = fetch(eve_id)
        if history is None:
            failures += 1
            if failures >= MAX_FAILURES:
                logger.warning("ESI %s stopped after %d failures in a row", model.__name__, failures)
                break
            continue
        failures = 0
        stored[eve_id], _created = model.objects.update_or_create(
            pk=eve_id, defaults={"history": history, "fetched_at": now}
        )
    return {
        eve_id: [(datetime.fromisoformat(start), value) for start, value in row.history]
        for eve_id, row in stored.items()
        if row.history
    }
