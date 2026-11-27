"""The stored result the pages show: the markers and the connections per Corporation.

The calculation reads the whole Alliance's wallet journals, mails and
contracts; done on every page view it grows with the Alliance. The task
``tasks.update_snapshot`` runs it, on a schedule or from the button on the
pages, and stores the result as JSON in one row. A page reads that row only.
"""

import json
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from functools import cached_property

from django.db import connection
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from allianceauth.services.hooks import get_extension_logger

from .affiliations import ALLIANCE, CHARACTER, CORPORATION, Entity
from .hostiles import alliance_standings, hostile_entities, network_blue_ids
from .markers import (
    BLUE_KILLS,
    CONTACTS,
    CONTRACT_REF_TYPES,
    CORP_CHANGES,
    CONTRACTS,
    LABELS,
    MAILS,
    MEMBERSHIP,
    OWNER_CHANGES,
    WALLET,
    CorporationTile,
    Marker,
    Suspect,
    Visitor,
    by_markers,
    corporation_tiles,
    million,
    roster,
)
from .models import BlueKill, ContactSource, FindingReview, Snapshot, SpyConfiguration
from .network import Connections, Link, Standing, affiliate, connections, drop_ours, kept_partners
from .tenure import load as load_tenure

logger = get_extension_logger(__name__)

MARKERS = "markers"
NETWORK = "network"
# the markers whose rows are cases of one own character with one counterpart, summed (user, 2026-11-27)
DEALINGS = (WALLET, CONTRACTS, MAILS)
# the markers reviewed per case, whose first tick fixes what the case holds
CASES = (MEMBERSHIP, CORP_CHANGES, OWNER_CHANGES, *DEALINGS)
AFFILIATIONS = "affiliations"
PHASE_LABELS = {MARKERS: _("Markers"), NETWORK: _("Network"), AFFILIATIONS: _("Affiliations")}
CATEGORY_LABELS = {
    CHARACTER: pgettext_lazy("EVE jargon", "Character"),
    CORPORATION: pgettext_lazy("EVE jargon", "Corporation"),
    ALLIANCE: pgettext_lazy("EVE jargon", "Alliance"),
}


def category_label(category: str):
    # shortcut: a counterpart nobody could resolve has no category and reads as a character, which the
    # wallet's parties nearly always are; upgrade when a Corporation without a lookup shows up wrong
    return CATEGORY_LABELS.get(category, CATEGORY_LABELS[CHARACTER])


def _no_step(_name: str) -> None:
    pass


@dataclass
class MainCharacter:
    """What the pages need of a main; the snapshot keeps no model instances."""

    character_id: int
    character_name: str
    corporation_id: int
    # stored for a visitor only, whose main's Corporation may have no tile to take them from
    corporation_name: str = ""
    corporation_ticker: str = ""


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
    def contracting_count(self) -> int:
        return sum(1 for account in self.accounts if account.contracting)

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
        step("tenure")
        # when each character was in the Alliance: what it did before or after does not count (user, 2026-11-23)
        tenure = load_tenure(config, members.characters, config.since())
        tiles = corporation_tiles(config, step=step, hostiles=hostile_list, members=members, tenure=tenure)
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
            set(config.ignored_network_characters or ()),
            {int(eve_id) for eve_id in config.ignored_network_counterparts or ()},
            tenure,
            config.network_min_connections,
        )
    step("affiliations")
    with measurement.phase(AFFILIATIONS):
        hostiles = {hostile.id: Standing(hostile.standing, hostile.sources) for hostile in hostile_list}
        def rows(*kinds):
            # a visitor whose main is in the Alliance is a suspect too: its rows come twice, affiliated alike
            return [
                row
                for tile in tiles
                for suspect in [*tile.suspects, *(visitor.suspect for visitor in tile.visitors)]
                for kind in kinds
                if kind in suspect.markers
                for row in suspect.markers[kind].rows
            ]

        dealing_rows, contact_rows = rows(*DEALINGS), rows(CONTACTS)
        entities = affiliate(
            found.values(),
            hostiles,
            {row["counterpart_id"] for row in dealing_rows} | {row["contact_id"] for row in contact_rows},
        )
        standings = {eve_id: standing for eve_id, standing in alliance_standings(config).items() if eve_id in entities}
        _affiliate_rows(dealing_rows, entities, hostiles, standings)
        _affiliate_rows(contact_rows, entities, hostiles, standings, "contact_id")
        _reference_rows(contact_rows, entities, hostiles)
        blues = network_blue_ids(config) if config.network_neutral else None
        found = kept_partners(found, blues)
        # a partner that was in our Alliance at the time is a member then, whatever Auth knows (user, 2026-11-24)
        found = drop_ours(found, tenure, entities, config.network_min_connections, blues)

    tile_ids = {tile.id for tile in tiles}
    visited = defaultdict(set)  # user -> the Corporations of the Alliance its characters are in
    for user_id, _character_id, _name, corporation_id, _alliance_id in members.characters:
        if corporation_id in tile_ids:
            visited[user_id].add(corporation_id)
    by_corporation = {}
    for account in found.values():
        # a main outside the Alliance has no tile: the account shows where its alts are (user, 2026-11-19)
        homes = [account.corporation_id] if account.corporation_id in tile_ids else visited[account.user_id]
        for corporation_id in homes:
            by_corporation.setdefault(corporation_id, []).append(account)
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
                "visitors": [_visitor_data(visitor) for visitor in tile.visitors],
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
        # what the Alliance itself holds for them, hostile or not: the Network table shows it for every party
        "standings": [[eve_id, str(standing)] for eve_id, standing in standings.items()],
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


def _affiliate_rows(rows: list, entities: dict, hostiles: dict, standings: dict, id_key: str = "counterpart_id") -> None:
    """Name the Corporation and Alliance of each counterpart or contact, with the standing of a hostile one.

    ``held`` is the standing the Alliance itself holds, for the row's party and each group, as the Network table
    shows it. A snapshot older than that has none: the tables show a dash until the next run.
    """

    def held(eve_id):
        # a number, unlike the hostile standing: the badge compares it with the bands
        standing = standings.get(eve_id)
        return None if standing is None else float(standing)

    def group(eve_id):
        if not eve_id:
            return None
        hostile = hostiles.get(eve_id)
        entity = entities.get(eve_id)
        return {
            "name": entity.name if entity else str(eve_id),
            "standing": str(hostile.standing) if hostile else None,
            "held": held(eve_id),
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
        row["held"] = held(row[id_key])
        row["corporation"] = group(corporation_id)
        row["alliance"] = group(alliance_id)


def _reference_rows(rows: list, entities: dict, hostiles: dict) -> None:
    """The standing that makes each contact hostile, with the sources that hold it: the contact's own,
    else its Corporation's, else its Alliance's - the closest reason, as in ``hostile_index``."""
    for row in rows:
        entity = entities.get(row["contact_id"])
        ids = [row["contact_id"], *((entity.corporation_id, entity.alliance_id) if entity else ())]
        hostile = next((hostiles[eve_id] for eve_id in ids if eve_id in hostiles), None)
        row["reference"] = hostile and {
            "standing": str(hostile.standing),
            "sources": [[name, str(standing)] for name, standing in hostile.sources],
        }


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


def _visitor_data(visitor: Visitor) -> dict:
    main = visitor.suspect.main
    return {
        **_suspect_data(visitor.suspect),
        "main_corporation_name": main.corporation_name,
        "main_corporation_ticker": main.corporation_ticker,
        "alts": [[character_id, name] for character_id, name in visitor.alts],
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
            [
                link.character_id,
                link.counterpart_id,
                link.payments,
                link.trades,
                str(link.isk),
                link.first,
                link.last,
                link.contracts,
                link.direction,
                link.contract_payments,
            ]
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
            "network_neutral",
            "network_blue_above",
            "network_min_connections",
            "ignored_contact_characters",
            "ignored_network_characters",
            "ignored_network_counterparts",
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
    rows = kill_rows(marker, reviews)
    open_rows = [row for row in rows if not row["cleared"]]
    if not open_rows:
        return None
    # the Corporation page heads each date with its open kills, to clear them in one go
    day_open = Counter(row["date"] for row in open_rows)
    for row in rows:
        row["day_open"] = day_open[row["date"]]
    return {
        **marker,
        # the cleared ones folded under the open ones (user, 2026-11-27); stable, so each part stays by date
        "rows": sorted(rows, key=lambda row: row["cleared"]),
        "count": len(open_rows),
        "details": [row["victim"] or row["corporation"] for row in open_rows],
        "character_ids": sorted({character_id for row in open_rows for character_id in row["character_ids"]}),
    }


def kill_rows(marker: dict, reviews: dict) -> list:
    """The rows of a stored blue kills marker with their reviews: one per killmail."""
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
    return rows


def finding_reviews(alliance_id: int) -> dict:
    """(kind, main ID, key) -> (cleared, note, items) of the findings someone reviewed; one query.

    Every review, the ones ticked off again too: a case of ISK, contracts or mails keeps its items after an untick.
    """
    reviews = FindingReview.objects.filter(alliance_id=alliance_id)
    return {
        (kind, main_id, key): (cleared, note, items)
        for kind, main_id, key, cleared, note, items in reviews.values_list(
            "kind", "main_id", "key", "cleared", "note", "items"
        )
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
    rows = contact_rows(marker, main_id, reviews)
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


def contact_rows(marker: dict, main_id: int, reviews: dict) -> list:
    """The rows of a stored contacts marker with their reviews: one per contact and standing."""
    rows = []
    for row in marker.get("rows", []):
        key = contact_key(row)
        cleared, note, _items = reviews.get((CONTACTS, main_id, key), (False, "", []))
        # the template cannot zip: each character with its ID for the EveWho link
        named = list(zip(row["character_ids"], row["characters"]))
        rows.append({**row, "key": key, "cleared": cleared, "note": note, "named_characters": named})
    # the cleared ones folded under the open ones (user, 2026-11-27)
    return sorted(rows, key=lambda row: row["cleared"])


def dealing_rows(marker: dict, main_id: int, reviews: dict) -> list:
    """The cases of a stored ISK, contracts or mails marker: per own character and counterpart, each reviewed case with
    the items it held when first cleared, the items left over one open case; the open cases first, the latest first.

    A case's key is "<character ID>:<counterpart ID>:<number>"; the open case takes the number after the last
    reviewed one, so its note stays with it until it is cleared (user, 2026-11-27).
    """
    cases = _reviewed_cases(marker["kind"], main_id, reviews)
    rows = []
    for row in marker.get("rows", []):
        if "items" not in row:
            # a snapshot of 0.1.5 or older holds no items to review until the next run
            rows.append(row)
            continue
        prefix = f"{row['character_id']}:{row['counterpart_id']}:"
        rows += _split(row, prefix, cases.get(prefix, {}), _case)
    return _open_first(rows)


def membership_rows(marker: dict, main_id: int, reviews: dict) -> list:
    """The cases of a stored Hostile membership marker: per hostile group, the memberships of the account's
    characters in it, split as ``dealing_rows`` does - a character joining it again, or one newly added to the
    account, is a new case (user, 2026-11-27). Keys: "<group ID>:<number>"."""
    cases = _reviewed_cases(marker["kind"], main_id, reviews)
    rows = []
    for row in marker.get("rows", []):
        prefix = f"{row['group_id']}:"
        rows += _split(row, prefix, cases.get(prefix, {}), _membership_case)
    return _open_first(rows)


def _split(row: dict, prefix: str, reviewed: dict, case) -> list:
    """Each reviewed case of ``row`` with the items it held when first cleared, the items left over one open case;
    ``case`` makes a row of a key, the tick, the note and items."""
    left = {item[0]: item for item in row["items"]}
    rows = []
    for number, (cleared, note, covered) in sorted(reviewed.items()):
        held = [left.pop(item_id) for item_id in covered if item_id in left]
        if held:
            rows.append(case(row, f"{prefix}{number}", cleared, note, held))
    if left:
        number, cleared, note = _open_case(reviewed)
        rows.append(case(row, f"{prefix}{number}", cleared, note, list(left.values())))
    return rows


def _membership_case(row: dict, key: str, cleared: bool, note: str, items: list) -> dict:
    """One case of a Hostile membership row: the group with the memberships in ``items`` alone."""
    items = sorted(items, key=lambda item: item[1], reverse=True)
    named = list(dict.fromkeys((item[3], item[2]) for item in items))
    days = [item[1] for item in items]
    return {
        **row,
        "key": key,
        "cleared": cleared,
        "note": note,
        "items": items,
        # each membership for the info button: day joined and character
        "entries": [(item[1], item[2], "0", "") for item in items],
        "count": len(items),
        # a membership Auth alone knows has no day
        "first": min(filter(None, days), default=""),
        "last": max(days),
        "named_characters": named,
    }


def owner_rows(marker: dict, main_id: int, reviews: dict) -> list:
    """The cases of a stored Owner changes marker: per character, its earlier owners, split as ``dealing_rows`` does -
    one more owner than a cleared case held is a new case. Keys: "<character ID>:<number>"."""
    cases = _reviewed_cases(marker["kind"], main_id, reviews)
    rows = []
    for row in marker.get("rows", []):
        prefix = f"{row['character_id']}:"
        rows += _split(row, prefix, cases.get(prefix, {}), _owner_case)
    return _open_first(rows)


def _owner_case(row: dict, key: str, cleared: bool, note: str, items: list) -> dict:
    """One case of an Owner changes row: the character with the earlier owners in ``items`` alone."""
    items = sorted(items, key=lambda item: item[1], reverse=True)
    days = [item[1] for item in items]
    return {
        **row,
        "key": key,
        "cleared": cleared,
        "note": note,
        "items": items,
        # each owner for the info button: the day Auth first saw them and their name
        "entries": [(item[1], item[2], "0", "") for item in items],
        "count": len(items),
        "first": min(days),
        "last": max(days),
        "named_characters": [(row["character_id"], row["character"])],
    }


def join_rows(marker: dict, main_id: int, reviews: dict) -> list:
    """The cases of a stored Corporation changes marker: per character, its joins of the last 365 days.

    A case cleared once keeps the joins it held; a join none of them holds reopens the character as a new case
    with every join of the year (user, 2026-11-27) - the number is the finding, not the one join. Keys as in
    ``dealing_rows``: "<character ID>:<number>".
    """
    cases = _reviewed_cases(marker["kind"], main_id, reviews)
    rows = []
    for row in marker.get("rows", []):
        if "items" not in row:
            # a snapshot of 0.1.5 or older holds no joins to review until the next run
            rows.append(row)
            continue
        prefix = f"{row['character_id']}:"
        reviewed = cases.get(prefix, {})
        covered = set()
        for number, (cleared, note, items) in sorted(reviewed.items()):
            held = [item for item in row["items"] if item[0] in items]
            covered.update(items)
            if held:
                rows.append(_join_case(row, f"{prefix}{number}", cleared, note, held))
        if any(item[0] not in covered for item in row["items"]):
            number, cleared, note = _open_case(reviewed)
            rows.append(_join_case(row, f"{prefix}{number}", cleared, note, row["items"]))
    return _open_first(rows)


def _reviewed_cases(kind: str, main_id: int, reviews: dict) -> dict:
    """The main's reviews of one marker by key prefix: "<...>:" -> {case number: (cleared, note, items)}."""
    cases = {}
    for (review_kind, review_main, key), review in reviews.items():
        if (review_kind, review_main) == (kind, main_id):
            prefix, _sep, number = key.rpartition(":")
            cases.setdefault(f"{prefix}:", {})[int(number)] = review
    return cases


def _open_case(reviewed: dict) -> tuple:
    """(number, cleared, note) of the open case: the number after the last case fixed by a tick, so its note stays
    with it until it is cleared (user, 2026-11-27)."""
    frozen = [number for number, review in reviewed.items() if review[2]]
    number = max(frozen) + 1 if frozen else 0
    cleared, note, _items = reviewed.get(number, (False, "", []))
    return number, cleared, note


def _open_first(rows: list) -> list:
    rows.sort(key=lambda row: row["last"], reverse=True)
    # stable: the latest first within the open and within the cleared ones
    return sorted(rows, key=lambda row: row.get("cleared", False))


def _join_case(row: dict, key: str, cleared: bool, note: str, items: list) -> dict:
    """One case of a Corporation changes row: the stored row counted over ``items`` (its joins) alone."""
    days = [item[1] for item in items]
    return {
        **row,
        "key": key,
        "cleared": cleared,
        "note": note,
        "items": items,
        # each join for the info button: day and Corporation, in the columns of a mail's day and kind
        "entries": [(item[1], item[2], "0", "") for item in items],
        "count": len(items),
        "first": min(days),
        "last": max(days),
        "named_characters": [(row["character_id"], row["character"])],
    }


def _case(row: dict, key: str, cleared: bool, note: str, items: list) -> dict:
    """One case of an ISK, contracts or mails row: the stored row with its sums taken over ``items`` alone."""
    isk = sum((Decimal(item[3]) for item in items), Decimal(0))
    days = [item[1] for item in items]
    return {
        **row,
        "key": key,
        "cleared": cleared,
        "note": note,
        "items": items,
        # each one for the info button: date, kind, ISK, and a mail's subject (None for ISK and contracts)
        "entries": [(item[1], item[2].replace("_", " "), item[3], item[4]) for item in items],
        "count": len(items),
        "isk": str(isk),
        "million": million(isk),
        # an undated mail adds no day; a case of undated mails alone has none
        "first": min(filter(None, days), default=""),
        "last": max(days),
        "types": sorted({item[2].replace("_", " ") for item in items}),
        "contract_payments": any(item[2] in CONTRACT_REF_TYPES for item in items),
        # the template cannot zip; one character, as the contacts' and kills' rows name theirs
        "named_characters": [(row["character_id"], row["character"])],
    }


def case_rows(marker: dict, main_id: int, reviews: dict) -> list:
    """The cases of a stored marker of ``CASES``."""
    rows = {MEMBERSHIP: membership_rows, CORP_CHANGES: join_rows, OWNER_CHANGES: owner_rows}.get(
        marker["kind"], dealing_rows
    )
    return rows(marker, main_id, reviews)


def reviewed_cases(marker: dict, main_id: int, reviews: dict) -> dict | None:
    """A stored marker of ``CASES`` with the reviews applied; None once every case is cleared.

    As ``reviewed_kills``: read at every view, a cleared case stays, folded, it only stops counting.
    """
    rows = case_rows(marker, main_id, reviews)
    if not rows or "key" not in rows[0]:
        # nothing to review in a snapshot of 0.1.5 or older
        return marker
    open_rows = [row for row in rows if not row["cleared"]]
    if not open_rows:
        return None
    # the Corporation page heads each date of a last interaction or join with its open cases, to clear them at once
    day_open = Counter(row["last"] for row in open_rows)
    for row in open_rows:
        row["day_open"] = day_open[row["last"]]
    if marker["kind"] == MEMBERSHIP:
        # as the calculation counts and names them: every membership, "character: group"
        count = sum(row["count"] for row in open_rows)
        details = sorted({f"{item[2]}: {row['group']}" for row in open_rows for item in row["items"]}, key=str.lower)
    elif marker["kind"] == CORP_CHANGES:
        # as the calculation counts: every join of each character
        count = sum(row["count"] for row in open_rows)
        details = [f"{row['character']}: {row['count']}" for row in open_rows]
    elif marker["kind"] == OWNER_CHANGES:
        # as the calculation counts and names them: every earlier owner, "character: owner"
        count = sum(row["count"] for row in open_rows)
        details = sorted(
            {f"{row['character']}: {item[2]}" for row in open_rows for item in row["items"]}, key=str.lower
        )
    else:
        # an entry, contract or mail two own characters hold counts once, as in the calculation
        count = len({item[0] for row in open_rows for item in row["items"]})
        details = sorted({row["counterpart"] for row in open_rows}, key=str.lower)
    return {
        **marker,
        "rows": rows,
        "count": count,
        "details": details,
        "character_ids": sorted({eve_id for row in open_rows for eve_id, _name in row["named_characters"]}),
    }


def _finding(kind: str, row: dict) -> str:
    """A case in a word: the hostile group, the number of joins, or the counterpart."""
    if kind == MEMBERSHIP:
        return row["group"]
    if kind == CORP_CHANGES:
        return str(row["count"])
    if kind == OWNER_CHANGES:
        return ", ".join(sorted({item[2] for item in row["items"]}, key=str.lower))
    return row["counterpart"]


def cleared_rows(markers: list, main_id: int, reviews: dict, findings: dict) -> list:
    """The findings of a main whose every finding is cleared, every marker in one list for one table."""
    rows = []
    for marker in markers:
        if marker["kind"] in CASES:
            rows += [
                {
                    "label": LABELS[marker["kind"]],
                    "date": row["last"],
                    "finding": _finding(marker["kind"], row),
                    "killmail_id": None,
                    "named_characters": row["named_characters"],
                    "note": row["note"],
                }
                for row in case_rows(marker, main_id, findings)
            ]
        elif marker["kind"] == BLUE_KILLS:
            rows += [
                {
                    "label": LABELS[BLUE_KILLS],
                    "date": row["date"],
                    "finding": row["victim"] or row["corporation"],
                    "killmail_id": row["killmail_id"],
                    "named_characters": row["named_characters"],
                    "note": row["note"],
                }
                for row in kill_rows(marker, reviews)
            ]
        else:
            rows += [
                {
                    "label": LABELS[CONTACTS],
                    "date": "",
                    "finding": f"{row['contact']} ({row['standing']})",
                    "killmail_id": None,
                    "named_characters": row["named_characters"],
                    "note": row["note"],
                }
                for row in contact_rows(marker, main_id, findings)
            ]
    return rows


class Report:
    """The stored snapshot as the pages need it; no further query.

    ``disabled`` are the markers switched off in the settings: the snapshot
    keeps them, the tiles leave them out, so switching one on again needs no
    recalculation. ``reviews`` are the blue kills reviewed since, from
    ``kill_reviews()``: a cleared one no longer counts. ``findings`` are the
    other findings reviewed, from ``finding_reviews()``, alike.
    """

    def __init__(self, snapshot: Snapshot, disabled=(), reviews=None, findings=None, highlights=()):
        self.built_at = snapshot.built_at
        data = snapshot.data
        self.alliance_id = data["alliance_id"]
        self.alliance_name = data["alliance_name"]
        self.highlights = frozenset(highlights)
        rows = data["corporations"]
        self.entities = {
            row[0]: Entity(row[0], row[1], row[2], row[3], row[4]) for row in data.get("entities", [])
        }
        self.hostiles = {
            eve_id: Standing(Decimal(standing), [(name, Decimal(value)) for name, value in sources])
            for eve_id, standing, sources in data.get("hostiles", [])
        }
        # a snapshot of 0.0.41 or older stores none: the Network table shows a dash until the next run
        self.standings = {eve_id: Decimal(standing) for eve_id, standing in data.get("standings", [])}
        self.tiles = [self._tile(row, set(disabled), reviews or {}, findings or {}) for row in rows]
        tile_ids = {tile.id for tile in self.tiles}
        for tile in self.tiles:
            for visitor in tile.visitors:
                visitor.page = visitor.suspect.main.corporation_id in tile_ids
        self.network_tiles = [self._network_tile(row) for row in rows]
        self.metrics = self._metrics(data.get("metrics"))

    @staticmethod
    def _suspect(stored, disabled, reviews, findings) -> tuple:
        """(the stored account with its open markers, the stored markers every finding of which is cleared)."""
        suspect = Suspect(
            stored["user_id"],
            MainCharacter(
                stored["main_id"],
                stored["main_name"],
                stored["corporation_id"],
                stored.get("main_corporation_name", ""),
                stored.get("main_corporation_ticker", ""),
            ),
            stored["character_count"],
        )
        done = []
        for stored_marker in stored["markers"]:
            if stored_marker["kind"] in disabled:
                continue
            marker = stored_marker
            if marker["kind"] == BLUE_KILLS:
                marker = reviewed_kills(marker, reviews)
            elif marker["kind"] == CONTACTS:
                marker = reviewed_contacts(marker, stored["main_id"], findings)
            elif marker["kind"] in CASES:
                marker = reviewed_cases(marker, stored["main_id"], findings)
            if marker is None:
                done.append(stored_marker)
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
        return suspect, done

    @classmethod
    def _tile(cls, row, disabled=frozenset(), reviews=None, findings=None) -> CorporationTile:
        reviews, findings = reviews or {}, findings or {}
        tile = CorporationTile(row["id"], row["name"], row["ticker"], row["mains"])
        for stored in row["suspects"]:
            suspect, done = cls._suspect(stored, disabled, reviews, findings)
            # a main marked only by switched-off markers or cleared findings is clean
            if suspect.markers:
                tile.suspects.append(suspect)
            elif done:
                # gone from the list above, its cleared findings would be nowhere on the page
                rows = cleared_rows(done, stored["main_id"], reviews, findings)
                tile.cleared.append({"main": suspect.main, "rows": rows})
        # a snapshot older than the visitors has none until the next run; a cleared visitor leaves the page
        for stored in row.get("visitors", []):
            suspect, _done = cls._suspect(stored, disabled, reviews, findings)
            if suspect.markers:
                tile.visitors.append(Visitor(suspect, [tuple(alt) for alt in stored["alts"]]))
        tile.cleared.sort(key=lambda cleared: cleared["main"].character_name.lower())
        if disabled or reviews or findings:
            # the stored order counted the switched-off markers and the cleared findings too
            tile.suspects.sort(key=by_markers)
            tile.visitors.sort(key=lambda visitor: by_markers(visitor.suspect))
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
            account.highlights = self.highlights
            account.standings = self.standings
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

    @cached_property
    def parties(self) -> dict:
        """EVE ID -> (name, category) of every counterpart of the Network and of its Corporation and Alliance."""
        # the Alliance and its Corporations are no counterpart (user, 2026-11-23); a snapshot older than that
        # rule may still hold them in a chain
        ours = {self.alliance_id, *(tile.id for tile in self.network_tiles)}
        parties = {}
        for tile in self.network_tiles:
            for account in tile.accounts:
                for counterpart_id in account.counterparts:
                    for eve_id in account.chain(counterpart_id):
                        if eve_id in ours:
                            continue
                        entity = self.entities.get(eve_id)
                        parties[eve_id] = (account._name(eve_id), entity.category if entity else "")
        return parties

    def suggestions(self) -> list[tuple]:
        """(category label, names) for the search box: every party once, characters first."""
        names = {}
        for name, category in self.parties.values():
            names.setdefault(name, category_label(category))
        groups = {label: [] for label in CATEGORY_LABELS.values()}
        for name, label in names.items():
            groups[label].append(name)
        return [(label, sorted(found, key=str.casefold)) for label, found in groups.items() if found]

    def search(self, query: str, eve_id: int | None = None) -> list[dict]:
        """The Network rows whose counterpart, Corporation or Alliance has ``query`` in its name, of every account.

        With ``eve_id`` (a highlight tile's link) the rows whose chain holds that party instead, as the tile counts
        them - a name match would also find every longer name containing it.

        Each row is the table row of ``Connections.rows`` plus its ``tile`` (the main's Corporation) and the
        account's ``main_id`` and ``main_name``, which the result table links on.
        """
        needle = query.strip().casefold()
        if not needle and eve_id is None:
            return []
        rows = []
        for tile in self.network_tiles:
            for account in tile.accounts:
                for row in account.rows:
                    if eve_id is not None:
                        found = eve_id in account.chain(row["counterpart_id"])
                    else:
                        groups = (row["corporation"] or {}, row["alliance"] or {})
                        names = (row["counterpart"], *(group.get("name", "") for group in groups))
                        found = any(needle in name.casefold() for name in names)
                    if found:
                        rows.append({**row, "tile": tile, "main_id": account.main_id, "main_name": account.main_name})
        return rows

    def _party(self, eve_id: int, fallback: str = "") -> dict:
        name, category = self.parties.get(eve_id) or (
            (self.entities[eve_id].name, self.entities[eve_id].category) if eve_id in self.entities else ("", "")
        )
        hostile = self.hostiles.get(eve_id)
        return {
            "id": eve_id,
            "name": name or fallback or str(eve_id),
            "category": category,
            "label": category_label(category),
            "held": self.standings.get(eve_id),
            "hostile": hostile.standing if hostile else None,
        }

    def highlight_tiles(self, highlights: dict) -> list[dict]:
        """One tile per highlighted party: its standings, its Corporation and Alliance, the accounts that deal with it.

        ``highlights`` is ``SpyConfiguration.highlight_counterparts``. A party matches an account when it is a
        counterpart of the account or the Corporation or Alliance of one - the chain the Network follows.
        """
        tiles = []
        for key, stored_name in highlights.items():
            eve_id = int(key)
            entity = self.entities.get(eve_id)
            groups = [group_id for group_id in (entity.corporation_id, entity.alliance_id) if group_id] if entity else []
            users = {
                account.user_id
                for tile in self.network_tiles
                for account in tile.accounts
                if any(eve_id in account.chain(counterpart_id) for counterpart_id in account.counterparts)
            }
            tiles.append(
                {
                    **self._party(eve_id, stored_name),
                    "groups": [self._party(group_id) for group_id in groups if group_id != eve_id],
                    "accounts": len(users),
                }
            )
        return tiles
