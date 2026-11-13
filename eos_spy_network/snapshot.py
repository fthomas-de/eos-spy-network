"""The stored result the pages show: the markers and the connections per Corporation.

The calculation reads the whole Alliance's wallet journals, mails and
contracts; done on every page view it grows with the Alliance. The task
``tasks.update_snapshot`` runs it, on a schedule or from the button on the
pages, and stores the result as JSON in one row. A page reads that row only.
"""

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import connection
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from allianceauth.services.hooks import get_extension_logger

from .affiliations import ALLIANCE, CORPORATION, Entity
from .hostiles import hostile_entities
from .markers import (
    BLUE_KILLS,
    CONTACTS,
    CONTRACTS,
    WALLET,
    CorporationTile,
    Marker,
    Suspect,
    by_markers,
    corporation_tiles,
    roster,
)
from .models import BlueKill, ContactSource, FindingReview, Snapshot, SpyConfiguration
from .network import Connections, Link, Standing, affiliate, connections, hostile_only

logger = get_extension_logger(__name__)

MARKERS = "markers"
NETWORK = "network"
AFFILIATIONS = "affiliations"
PHASE_LABELS = {MARKERS: _("Markers"), NETWORK: _("Network"), AFFILIATIONS: _("Affiliations")}


def _no_step(_name: str) -> None:
    pass


@dataclass
class MainCharacter:
    """What the pages need of a main; the snapshot keeps no model instances."""

    character_id: int
    character_name: str
    corporation_id: int


@dataclass
class NetworkTile:
    id: int
    name: str
    ticker: str
    mains: int = 0
    # only accounts with a connection outside the Alliance, the most connected first
    accounts: list = field(default_factory=list)

    @property
    def shared_count(self) -> int:
        return sum(1 for account in self.accounts if account.shared)

    @property
    def trading_count(self) -> int:
        return sum(1 for account in self.accounts if account.trading)

    @property
    def hostile_count(self) -> int:
        return sum(1 for account in self.accounts if account.hostile)


class Measurement:
    """Times the phases of a calculation and counts its database queries."""

    def __init__(self):
        self.phases = {}
        self.queries = 0
        self.query_seconds = 0.0
        self.seconds = 0.0

    def _count_query(self, execute, sql, params, many, context):
        started = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.queries += 1
            self.query_seconds += time.perf_counter() - started

    @contextmanager
    def phase(self, name):
        started = time.perf_counter()
        with connection.execute_wrapper(self._count_query):
            yield
        elapsed = time.perf_counter() - started
        self.phases[name] = round(elapsed, 2)
        self.seconds += elapsed


def build(config: SpyConfiguration, step=_no_step) -> dict | None:
    """The data to store; None without an Alliance. ``step`` is told each step as it starts."""
    if not config.alliance:
        return None
    measurement = Measurement()
    stats = {}
    with measurement.phase(MARKERS):
        # both read once here, for the markers and the network alike
        hostile_list = hostile_entities(config)
        members = roster(config)
        tiles = corporation_tiles(config, step=step, hostiles=hostile_list, members=members)
    step("connections")
    mains = members.mains
    with measurement.phase(NETWORK):
        found = connections(
            mains,
            config.alliance.alliance_id,
            stats,
            config.since(),
            config.ignored_ref_types or (),
            members.characters,
        )
    step("affiliations")
    with measurement.phase(AFFILIATIONS):
        hostiles = {hostile.id: Standing(hostile.standing, hostile.sources) for hostile in hostile_list}
        def rows(*kinds):
            return [
                row
                for tile in tiles
                for suspect in tile.suspects
                for kind in kinds
                if kind in suspect.markers
                for row in suspect.markers[kind].rows
            ]

        dealing_rows, contact_rows = rows(WALLET, CONTRACTS), rows(CONTACTS)
        entities = affiliate(
            found.values(),
            hostiles,
            {row["counterpart_id"] for row in dealing_rows} | {row["contact_id"] for row in contact_rows},
        )
        _affiliate_rows(dealing_rows, entities, hostiles)
        _affiliate_rows(contact_rows, entities, hostiles, "contact_id")
        found = hostile_only(found)

    by_corporation = {}
    for account in found.values():
        by_corporation.setdefault(account.corporation_id, []).append(account)
    data = {
        "alliance_id": config.alliance.alliance_id,
        "alliance_name": config.alliance.alliance_name,
        "corporations": [
            {
                "id": tile.id,
                "name": tile.name,
                "ticker": tile.ticker,
                "mains": tile.mains,
                "suspects": [_suspect_data(suspect) for suspect in tile.suspects],
                "connections": [
                    _connections_data(account)
                    for account in sorted(
                        by_corporation.get(tile.id, []),
                        key=lambda account: (-len(account.counterparts), account.main_name.lower()),
                    )
                ],
            }
            for tile in tiles
        ],
        # once for every account: the counterparts' Corporations and Alliances, and the hostile ones
        "entities": [
            [entity.id, entity.name, entity.category, entity.corporation_id, entity.alliance_id]
            for entity in entities.values()
        ],
        "hostiles": [
            [eve_id, str(hostile.standing), [[name, str(standing)] for name, standing in hostile.sources]]
            for eve_id, hostile in hostiles.items()
            # only what a graph can show; the full hostile list would bloat the row
            if eve_id in entities
        ],
    }
    data["metrics"] = {
        "seconds": round(measurement.seconds, 2),
        "phases": measurement.phases,
        "queries": measurement.queries,
        "query_seconds": round(measurement.query_seconds, 2),
        "corporations": len(tiles),
        "accounts": len(mains),
        "characters": stats.get("characters", 0),
        "journal_entries": stats.get("journal_entries", 0),
        "payload_bytes": len(json.dumps(data)),
    }
    return data


def _affiliate_rows(rows: list, entities: dict, hostiles: dict, id_key: str = "counterpart_id") -> None:
    """Name the Corporation and Alliance of each counterpart or contact, with the standing of a hostile one."""

    def group(eve_id):
        if not eve_id:
            return None
        hostile = hostiles.get(eve_id)
        entity = entities.get(eve_id)
        return {
            "name": entity.name if entity else str(eve_id),
            "standing": str(hostile.standing) if hostile else None,
        }

    for row in rows:
        entity = entities.get(row[id_key])
        category = entity.category if entity else ""
        if category == CORPORATION:
            corporation_id, alliance_id = row[id_key], entity.alliance_id
        elif category == ALLIANCE:
            corporation_id, alliance_id = None, row[id_key]
        else:
            corporation_id = entity.corporation_id if entity else None
            alliance_id = entity.alliance_id if entity else None
        row["category"] = category
        row["corporation"] = group(corporation_id)
        row["alliance"] = group(alliance_id)


def _suspect_data(suspect: Suspect) -> dict:
    return {
        "user_id": suspect.user_id,
        "main_id": suspect.main.character_id,
        "main_name": suspect.main.character_name,
        "corporation_id": suspect.main.corporation_id,
        "character_count": suspect.character_count,
        "markers": [
            {
                "kind": marker.kind,
                "count": marker.count,
                "details": marker.sorted_details,
                "rows": marker.rows,
                "character_ids": sorted(marker.character_ids),
            }
            for marker in suspect.marker_list
        ],
    }


def _connections_data(account: Connections) -> dict:
    return {
        "user_id": account.user_id,
        "main_id": account.main_id,
        "main_name": account.main_name,
        "corporation_id": account.corporation_id,
        "characters": [[character_id, name] for character_id, name in account.characters.items()],
        "counterparts": [[counterpart_id, name] for counterpart_id, name in account.counterparts.items()],
        "links": [
            [link.character_id, link.counterpart_id, link.payments, link.trades, str(link.isk), link.first, link.last]
            for link in account.links
        ],
    }


def _inputs() -> tuple:
    """Every setting a calculation reads, to tell whether one changed while it ran."""
    return (
        SpyConfiguration.objects.filter(pk=SpyConfiguration.singleton_instance_id)
        .values_list(
            "alliance_id",
            "hostile_below",
            "blue_from",
            "min_kill_value",
            "ignored_ships",
            "corp_changes_per_year",
            "lookback_days",
            "ignored_ref_types",
        )
        .first(),
        sorted(ContactSource.objects.values_list("kind", "entity_id")),
    )


def update(step=_no_step) -> Snapshot | None:
    """Recalculate and store; without an Alliance the old result goes."""
    # a save during the run queues nothing - QueueOnce drops it - so the run repeats itself once
    # shortcut: one repeat only, a third save in a row waits for the next run
    for _attempt in range(2):
        inputs = _inputs()
        data = build(SpyConfiguration.get_solo(), step)
        if _inputs() == inputs:
            break
    step("saving")
    if data is None:
        Snapshot.objects.all().delete()
        return None
    snapshot, _created = Snapshot.objects.update_or_create(
        pk=1, defaults={"built_at": timezone.now(), "data": data}
    )
    logger.info("Snapshot built for %s in %s s", data["alliance_name"], data["metrics"]["seconds"])
    return snapshot


def current() -> Snapshot | None:
    return Snapshot.objects.filter(pk=1).first()


def kill_reviews(alliance_id: int) -> dict:
    """(character ID, killmail ID) -> (cleared, note) of the blue kills someone reviewed; one query."""
    reviewed = BlueKill.objects.filter(alliance_id=alliance_id).filter(Q(cleared=True) | ~Q(note=""))
    return {
        (character_id, killmail_id): (cleared, note)
        for character_id, killmail_id, cleared, note in reviewed.values_list(
            "character_id", "killmail_id", "cleared", "note"
        )
    }


def reviewed_kills(marker: dict, reviews: dict) -> dict | None:
    """A stored blue kills marker with the reviews applied; None once every kill is cleared.

    Read at every view, not stored: a tick takes effect at once, without a
    recalculation. A cleared kill stays in the rows, it only stops counting.
    """
    # the marker is one main's: one row per killmail, its characters together (the user's rule)
    groups = {}
    for row in marker.get("rows", []):
        cleared, note = reviews.get((row["character_id"], row["killmail_id"]), (False, ""))
        group = groups.get(row["killmail_id"])
        if group is None:
            groups[row["killmail_id"]] = {
                **row,
                "names": [row["character"]],
                "character_ids": [row["character_id"]],
                "cleared": cleared,
                "note": note,
            }
            continue
        group["names"].append(row["character"])
        group["character_ids"].append(row["character_id"])
        # kill_note writes the group at once; a row reviewed alone before keeps the group open
        group["cleared"] = group["cleared"] and cleared
        group["note"] = group["note"] or note
    rows = []
    for group in groups.values():
        names = group.pop("names")
        # the template cannot zip: each character with its ID for the EveWho link
        named = list(zip(group["character_ids"], names))
        rows.append({**group, "character": ", ".join(names), "named_characters": named})
    open_rows = [row for row in rows if not row["cleared"]]
    if not open_rows:
        return None
    return {
        **marker,
        "rows": rows,
        "count": len(open_rows),
        "details": [row["victim"] or row["corporation"] for row in open_rows],
        "character_ids": sorted({character_id for row in open_rows for character_id in row["character_ids"]}),
    }


def finding_reviews(alliance_id: int) -> dict:
    """(kind, main ID, key) -> (cleared, note) of the findings someone reviewed; one query."""
    reviewed = FindingReview.objects.filter(alliance_id=alliance_id).filter(Q(cleared=True) | ~Q(note=""))
    return {
        (kind, main_id, key): (cleared, note)
        for kind, main_id, key, cleared, note in reviewed.values_list("kind", "main_id", "key", "cleared", "note")
    }


def contact_key(row: dict) -> str:
    """A friendly hostile contact's finding: a review holds for this standing only, another one is new."""
    return f"{row['contact_id']}:{row['standing']}"


def reviewed_contacts(marker: dict, main_id: int, reviews: dict) -> dict | None:
    """A stored contacts marker with the reviews applied; None once every contact is cleared.

    As ``reviewed_kills``: read at every view, a cleared row stays, it only stops counting.
    """
    if not marker.get("rows"):
        # a snapshot of 0.0.15 or older has no rows to review until the next run
        return marker
    rows = []
    for row in marker["rows"]:
        key = contact_key(row)
        cleared, note = reviews.get((CONTACTS, main_id, key), (False, ""))
        # the template cannot zip: each character with its ID for the EveWho link
        named = list(zip(row["character_ids"], row["characters"]))
        rows.append({**row, "key": key, "cleared": cleared, "note": note, "named_characters": named})
    open_rows = [row for row in rows if not row["cleared"]]
    if not open_rows:
        return None
    return {
        **marker,
        "rows": rows,
        "count": len(open_rows),
        "details": [f"{row['contact']} ({row['standing']})" for row in open_rows],
        "character_ids": sorted({character_id for row in open_rows for character_id in row["character_ids"]}),
    }


class Report:
    """The stored snapshot as the pages need it; no further query.

    ``disabled`` are the markers switched off in the settings: the snapshot
    keeps them, the tiles leave them out, so switching one on again needs no
    recalculation. ``reviews`` are the blue kills reviewed since, from
    ``kill_reviews()``: a cleared one no longer counts. ``findings`` are the
    other findings reviewed, from ``finding_reviews()``, alike.
    """

    def __init__(self, snapshot: Snapshot, disabled=(), reviews=None, findings=None):
        self.built_at = snapshot.built_at
        data = snapshot.data
        self.alliance_id = data["alliance_id"]
        self.alliance_name = data["alliance_name"]
        rows = data["corporations"]
        self.entities = {
            row[0]: Entity(row[0], row[1], row[2], row[3], row[4]) for row in data.get("entities", [])
        }
        self.hostiles = {
            eve_id: Standing(Decimal(standing), [(name, Decimal(value)) for name, value in sources])
            for eve_id, standing, sources in data.get("hostiles", [])
        }
        self.tiles = [self._tile(row, set(disabled), reviews or {}, findings or {}) for row in rows]
        self.network_tiles = [self._network_tile(row) for row in rows]
        self.metrics = self._metrics(data.get("metrics"))

    @staticmethod
    def _tile(row, disabled=frozenset(), reviews=None, findings=None) -> CorporationTile:
        tile = CorporationTile(row["id"], row["name"], row["ticker"], row["mains"])
        for stored in row["suspects"]:
            suspect = Suspect(
                stored["user_id"],
                MainCharacter(stored["main_id"], stored["main_name"], stored["corporation_id"]),
                stored["character_count"],
            )
            for marker in stored["markers"]:
                if marker["kind"] in disabled:
                    continue
                if marker["kind"] == BLUE_KILLS:
                    marker = reviewed_kills(marker, reviews or {})
                elif marker["kind"] == CONTACTS:
                    marker = reviewed_contacts(marker, stored["main_id"], findings or {})
                if marker is None:
                    continue
                suspect.markers[marker["kind"]] = Marker(
                    marker["kind"],
                    marker["count"],
                    set(marker["details"]),
                    # a snapshot of 0.0.4 or older has no rows, one of 0.0.9 or older no characters,
                    # until the next run
                    marker.get("rows", []),
                    set(marker.get("character_ids", [])),
                )
            # a main marked only by switched-off markers or cleared findings is clean
            if suspect.markers:
                tile.suspects.append(suspect)
        if disabled or reviews or findings:
            # the stored order counted the switched-off markers and the cleared findings too
            tile.suspects.sort(key=by_markers)
        return tile

    def _network_tile(self, row) -> NetworkTile:
        tile = NetworkTile(row["id"], row["name"], row["ticker"], row["mains"])
        for stored in row.get("connections", []):
            account = Connections(stored["user_id"], stored["main_id"], stored["main_name"], stored["corporation_id"])
            account.characters = dict(stored["characters"])
            account.counterparts = dict(stored["counterparts"])
            # a snapshot of 0.0.4 or older stores no period
            account.links = [
                Link(character_id, counterpart_id, payments, trades, Decimal(isk), *period)
                for character_id, counterpart_id, payments, trades, isk, *period in stored["links"]
            ]
            account.entities = self.entities
            account.hostiles = self.hostiles
            tile.accounts.append(account)
        return tile

    @staticmethod
    def _metrics(stored) -> dict | None:
        if not stored:
            return None
        return {
            **stored,
            "kilobytes": round(stored["payload_bytes"] / 1024),
            "phases": [(PHASE_LABELS[phase], seconds) for phase, seconds in stored["phases"].items() if phase in PHASE_LABELS],
        }

    def tile(self, corporation_id: int) -> CorporationTile | None:
        return next((tile for tile in self.tiles if tile.id == corporation_id), None)

    def network_tile(self, corporation_id: int) -> NetworkTile | None:
        return next((tile for tile in self.network_tiles if tile.id == corporation_id), None)
