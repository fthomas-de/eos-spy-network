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
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from allianceauth.authentication.models import UserProfile
from allianceauth.services.hooks import get_extension_logger

from .markers import CorporationTile, Marker, Suspect, corporation_tiles
from .models import Snapshot, SpyConfiguration
from .network import Connections, Link, connections

logger = get_extension_logger(__name__)

MARKERS = "markers"
NETWORK = "network"
PHASE_LABELS = {MARKERS: _("Markers"), NETWORK: _("Network")}


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


def build(config: SpyConfiguration) -> dict | None:
    """The data to store; None without an Alliance."""
    if not config.alliance:
        return None
    measurement = Measurement()
    stats = {}
    with measurement.phase(MARKERS):
        tiles = corporation_tiles(config)
    with measurement.phase(NETWORK):
        mains = {
            profile.user_id: profile.main_character
            for profile in UserProfile.objects.filter(
                main_character__corporation_id__in=[tile.id for tile in tiles]
            ).select_related("main_character")
        }
        found = connections(mains, config.alliance.alliance_id, stats)

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


def _suspect_data(suspect: Suspect) -> dict:
    return {
        "user_id": suspect.user_id,
        "main_id": suspect.main.character_id,
        "main_name": suspect.main.character_name,
        "corporation_id": suspect.main.corporation_id,
        "character_count": suspect.character_count,
        "markers": [
            {"kind": marker.kind, "count": marker.count, "details": marker.sorted_details}
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
            [link.character_id, link.counterpart_id, link.payments, link.trades, str(link.isk)]
            for link in account.links
        ],
    }


def update() -> Snapshot | None:
    """Recalculate and store; without an Alliance the old result goes."""
    data = build(SpyConfiguration.get_solo())
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


class Report:
    """The stored snapshot as the pages need it; no further query."""

    def __init__(self, snapshot: Snapshot):
        self.built_at = snapshot.built_at
        data = snapshot.data
        self.alliance_id = data["alliance_id"]
        self.alliance_name = data["alliance_name"]
        rows = data["corporations"]
        self.tiles = [self._tile(row) for row in rows]
        self.network_tiles = [self._network_tile(row) for row in rows]
        self.metrics = self._metrics(data.get("metrics"))

    @staticmethod
    def _tile(row) -> CorporationTile:
        tile = CorporationTile(row["id"], row["name"], row["ticker"], row["mains"])
        for stored in row["suspects"]:
            suspect = Suspect(
                stored["user_id"],
                MainCharacter(stored["main_id"], stored["main_name"], stored["corporation_id"]),
                stored["character_count"],
            )
            for marker in stored["markers"]:
                suspect.markers[marker["kind"]] = Marker(marker["kind"], marker["count"], set(marker["details"]))
            tile.suspects.append(suspect)
        return tile

    @staticmethod
    def _network_tile(row) -> NetworkTile:
        tile = NetworkTile(row["id"], row["name"], row["ticker"], row["mains"])
        for stored in row.get("connections", []):
            account = Connections(stored["user_id"], stored["main_id"], stored["main_name"], stored["corporation_id"])
            account.characters = dict(stored["characters"])
            account.counterparts = dict(stored["counterparts"])
            account.links = [
                Link(character_id, counterpart_id, payments, trades, Decimal(isk))
                for character_id, counterpart_id, payments, trades, isk in stored["links"]
            ]
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
