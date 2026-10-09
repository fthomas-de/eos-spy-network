"""ISK connections of an account to characters outside the Alliance.

Two kinds of connection make an account show up:

- a shared counterpart: at least two characters of the account - the main and
  an alt, or two alts - exchanged ISK with the same character outside the
  Alliance. One payment each is enough; it is the overlap that tells.
- player trading: any trade window deal of one of the account's characters
  with someone outside the Alliance.

"Outside" is whatever Auth does not know as part of the Alliance: a
character Auth has never seen counts as outside, since the app makes no ESI
call to look its affiliation up. NPCs (agents, NPC Corporations, factions)
never count - bounties and taxes would connect every ratter.

The data is corptools' wallet journal; without corptools there is none.

Each counterpart is then followed to its Corporation and Alliance
(``affiliations``); a hostile standing on any of the three makes it a hostile
partner, and the graph shows the chain up to the entity that carries it.
Only hostile partners stay (``hostile_only``): sharing a trader or a hauler
outside the Alliance is everyday business in EVE, sharing a hostile is not.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from django.apps import apps
from django.db.models import Q

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

TRADING = "player_trading"
# ISK moved between two parties on purpose: donations, trades, contracts
PAYMENT_REF_TYPES = (
    "player_donation",
    TRADING,
    "contract_price",
    "contract_price_payment_corp",
    "contract_reward",
    "contract_collateral",
    "contract_collateral_payout",
)

# factions 500000-599999, NPC Corporations 1000000-1999999, agents 3000000-3999999
NPC_IDS = range(500_000, 4_000_000)


@dataclass
class Link:
    character_id: int
    counterpart_id: int
    payments: int = 0
    trades: int = 0
    isk: Decimal = Decimal(0)
    # the first and the last payment, as ISO dates: the snapshot stores JSON
    first: str | None = None
    last: str | None = None

    def add(self, day: str, trade: bool, isk) -> None:
        self.payments += 1
        if trade:
            self.trades += 1
        self.isk += abs(isk or 0)
        self.first = min(self.first or day, day)
        self.last = max(self.last or day, day)


# the columns of the graph, left to right: own side, partners, their groups
LEVELS = {"main": 0, "alt": 1, "partner": 2, "corporation": 3, "alliance": 4}


@dataclass
class Standing:
    """A hostile contact: the lowest standing, and each source that holds it."""

    standing: Decimal
    sources: list = field(default_factory=list)  # [(source name, standing)]


@dataclass
class Connections:
    user_id: int
    main_id: int
    main_name: str
    corporation_id: int
    # every character of the account, the main among them
    characters: dict = field(default_factory=dict)
    # counterpart ID -> name, only those that made the account show up
    counterparts: dict = field(default_factory=dict)
    links: list = field(default_factory=list)
    # EVE ID -> affiliations.Entity of the counterparts and their groups; shared by all accounts
    entities: dict = field(default_factory=dict)
    # EVE ID -> Standing of every hostile contact; shared as well
    hostiles: dict = field(default_factory=dict)

    @property
    def shared(self) -> set:
        """The counterparts at least two own characters exchanged ISK with."""
        characters = defaultdict(set)
        for link in self.links:
            characters[link.counterpart_id].add(link.character_id)
        return {counterpart_id for counterpart_id, own in characters.items() if len(own) >= 2}

    @property
    def trading(self) -> set:
        return {link.counterpart_id for link in self.links if link.trades}

    def chain(self, counterpart_id: int) -> list[int]:
        """The counterpart, its Corporation and its Alliance, as far as they are known."""
        entity = self.entities.get(counterpart_id)
        if entity is None:
            return [counterpart_id]
        chain = [counterpart_id]
        for group_id in (entity.corporation_id, entity.alliance_id):
            if group_id and group_id not in chain:
                chain.append(group_id)
        return chain

    def reason(self, counterpart_id: int) -> int | None:
        """The entity of the chain whose hostile standing makes the counterpart hostile; the closest wins."""
        return next((eve_id for eve_id in self.chain(counterpart_id) if eve_id in self.hostiles), None)

    @property
    def hostile(self) -> set:
        return {counterpart_id for counterpart_id in self.counterparts if self.reason(counterpart_id)}

    def _name(self, eve_id) -> str:
        entity = self.entities.get(eve_id)
        return self.counterparts.get(eve_id) or (entity.name if entity else "") or str(eve_id)

    def _group(self, eve_id) -> dict | None:
        """Name and standing of a Corporation or Alliance, for a table cell."""
        if not eve_id:
            return None
        hostile = self.hostiles.get(eve_id)
        return {"name": self._name(eve_id), "standing": hostile.standing if hostile else None}

    @property
    def rows(self) -> list[dict]:
        """One per link, for the table under the graph."""
        rows = []
        for link in self.links:
            entity = self.entities.get(link.counterpart_id)
            corporation_id = entity.corporation_id if entity else None
            alliance_id = entity.alliance_id if entity else None
            rows.append(
                {
                    "character": self.characters.get(link.character_id, str(link.character_id)),
                    "counterpart": self._name(link.counterpart_id),
                    "hostile": self.reason(link.counterpart_id) is not None,
                    "corporation": self._group(corporation_id),
                    "alliance": self._group(alliance_id),
                    "payments": link.payments,
                    "trades": link.trades,
                    "isk": link.isk,
                    "first": link.first,
                    "last": link.last,
                }
            )
        return rows

    def _node(self, eve_id, kind: str) -> dict:
        hostile = self.hostiles.get(eve_id)
        node = {
            "id": eve_id,
            "label": self._name(eve_id),
            # hostile_partner, hostile_corporation ...: the red tones in network.js
            "group": f"hostile_{kind}" if hostile else kind,
            "level": LEVELS[kind],
        }
        if hostile:
            node["standing"] = str(hostile.standing)
            node["sources"] = [[name, str(standing)] for name, standing in hostile.sources]
        return node

    def graph(self) -> dict:
        """Nodes and edges for network.js; groups name the colours there, levels the columns."""
        linked = {link.character_id for link in self.links}
        nodes = {}
        edges = []
        for character_id, name in self.characters.items():
            # an alt without a link would float alone; the main stays as the anchor
            if character_id in linked or character_id == self.main_id:
                kind = "main" if character_id == self.main_id else "alt"
                nodes[character_id] = {"id": character_id, "label": name, "group": kind, "level": LEVELS[kind]}
                if kind == "alt":
                    edges.append({"from": self.main_id, "to": character_id, "kind": "account"})

        for counterpart_id in self.counterparts:
            chain = self.chain(counterpart_id)
            reason = self.reason(counterpart_id)
            node = self._node(counterpart_id, "partner")
            if reason is not None and node["group"] == "partner":
                # hostile through its Corporation or Alliance: red as well, the reason sits further right
                node["group"] = "hostile_partner"
            # the groups behind the reason only crowd the graph; the tooltip still names them
            node["affiliation"] = [self._name(group_id) for group_id in chain[1:]]
            chain = chain[: chain.index(reason) + 1] if reason is not None else chain[:1]
            nodes.setdefault(counterpart_id, node)
            for child, parent in zip(chain, chain[1:]):
                entity = self.entities.get(parent)
                kind = ALLIANCE_KIND if entity and entity.category == "alliance" else "corporation"
                nodes.setdefault(parent, self._node(parent, kind))
                edge = {"from": child, "to": parent, "kind": "member"}
                if edge not in edges:
                    edges.append(edge)

        edges += [
            {
                "from": link.character_id,
                "to": link.counterpart_id,
                "kind": "trading" if link.trades else "payment",
                "payments": link.payments,
                "trades": link.trades,
                "first": link.first,
                "last": link.last,
            }
            for link in self.links
        ]
        return {"nodes": list(nodes.values()), "edges": edges}


ALLIANCE_KIND = "alliance"


def affiliate(accounts, hostiles: dict) -> dict:
    """Look up the Corporation and Alliance of every counterpart and hand them to the accounts.

    ``hostiles`` maps the ID of every hostile contact to its Standing. Returns
    the entities, which the snapshot stores once for all accounts.
    """
    from .affiliations import resolve

    accounts = list(accounts)
    entities = resolve({counterpart_id for account in accounts for counterpart_id in account.counterparts})
    for account in accounts:
        account.entities = entities
        account.hostiles = hostiles
    return entities


def hostile_only(accounts: dict) -> dict:
    """The accounts cut down to their hostile partners, by user ID; an account without one goes.

    Needs the affiliations (``affiliate``) first: a partner is often hostile
    only through its Corporation or Alliance.
    """
    result = {}
    for user_id, account in accounts.items():
        hostile = account.hostile
        if not hostile:
            continue
        account.links = [link for link in account.links if link.counterpart_id in hostile]
        account.counterparts = {
            counterpart_id: name for counterpart_id, name in account.counterparts.items() if counterpart_id in hostile
        }
        result[user_id] = account
    return result


def alliance_ids(alliance_id: int) -> set[int]:
    """Every ID Auth knows as part of the Alliance: itself, its Corporations, their characters."""
    corporations = set(
        EveCorporationInfo.objects.filter(alliance__alliance_id=alliance_id).values_list("corporation_id", flat=True)
    )
    characters = EveCharacter.objects.filter(Q(alliance_id=alliance_id) | Q(corporation_id__in=corporations))
    return {alliance_id, *corporations, *characters.values_list("character_id", flat=True)}


def connections(mains: dict, alliance_id: int, stats: dict | None = None) -> dict:
    """The accounts with connections outside the Alliance, by user ID.

    ``mains`` maps the user ID of every account to check to its main
    EveCharacter. ``stats`` gets the number of journal entries read.
    """
    if stats is not None:
        stats["journal_entries"] = 0
        stats["characters"] = 0
    if not mains or not apps.is_installed("corptools"):
        return {}
    from corptools.models import CharacterWalletJournalEntry

    owner = {}
    names = {}
    for user_id, character_id, name in CharacterOwnership.objects.filter(user_id__in=mains).values_list(
        "user_id", "character__character_id", "character__character_name"
    ):
        owner[character_id] = user_id
        names[character_id] = name
    if stats is not None:
        stats["characters"] = len(owner)
    inside = alliance_ids(alliance_id)

    # (user, own character, counterpart) -> link
    links = {}
    counterpart_names = {}
    entries = CharacterWalletJournalEntry.objects.filter(
        character__character__character_id__in=list(owner), ref_type__in=PAYMENT_REF_TYPES
    ).values_list(
        "character__character__character_id",
        "ref_type",
        "amount",
        "date",
        "first_party_id",
        "first_party_name__name",
        "second_party_id",
        "second_party_name__name",
    )
    for character_id, ref_type, amount, date, first_id, first_name, second_id, second_name in entries.iterator():
        if stats is not None:
            stats["journal_entries"] += 1
        user_id = owner[character_id]
        for party_id, party_name in ((first_id, first_name), (second_id, second_name)):
            # an own alt, a member of the Alliance or an NPC is no connection outside
            if not party_id or party_id in inside or party_id in NPC_IDS or owner.get(party_id) == user_id:
                continue
            link = links.get((user_id, character_id, party_id))
            if link is None:
                link = links[(user_id, character_id, party_id)] = Link(character_id, party_id)
            link.add(date.date().isoformat(), ref_type == TRADING, amount)
            if party_name:
                counterpart_names[party_id] = party_name

    by_user = defaultdict(list)
    for (user_id, _character_id, _counterpart_id), link in links.items():
        by_user[user_id].append(link)

    result = {}
    for user_id, user_links in by_user.items():
        main = mains[user_id]
        account = Connections(user_id, main.character_id, main.character_name, main.corporation_id)
        account.links = user_links
        keep = account.shared | account.trading
        if not keep:
            continue
        account.links = sorted(
            (link for link in user_links if link.counterpart_id in keep),
            key=lambda link: (-link.payments, link.character_id, link.counterpart_id),
        )
        account.characters = {
            character_id: name for character_id, name in names.items() if owner[character_id] == user_id
        }
        account.counterparts = {counterpart_id: counterpart_names.get(counterpart_id) for counterpart_id in keep}
        result[user_id] = account

    _fill_names([account.counterparts for account in result.values()])
    return result


def _fill_names(tables: list[dict]) -> None:
    """Names the journal left empty, from Auth's tables and corptools' names; else the ID."""
    missing = {eve_id for table in tables for eve_id, name in table.items() if not name}
    if not missing:
        return
    found = dict(
        EveCharacter.objects.filter(character_id__in=missing).values_list("character_id", "character_name")
    )
    found.update(
        EveCorporationInfo.objects.filter(corporation_id__in=missing).values_list("corporation_id", "corporation_name")
    )
    from corptools.models import EveName

    found.update(EveName.objects.filter(eve_id__in=missing - set(found)).values_list("eve_id", "name"))
    for table in tables:
        for eve_id, name in table.items():
            if not name:
                table[eve_id] = found.get(eve_id, str(eve_id))
