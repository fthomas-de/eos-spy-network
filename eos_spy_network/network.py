"""ISK connections of an account to characters outside the Alliance.

Three kinds of connection make an account show up:

- a shared counterpart: at least two characters of the account - the main and
  an alt, or two alts - exchanged ISK or a contract without ISK with the same
  character outside the Alliance. One payment each is enough; it is the
  overlap that tells.
- player trading: any trade window deal of one of the account's characters
  with someone outside the Alliance.
- a private contract with items: any one, with or without ISK, counted apart
  from the payments.

"Outside" is whatever Auth does not know as part of the Alliance: a
character Auth has never seen counts as outside until its affiliation is
looked up (``affiliate``); one whose Corporation or Alliance is ours then goes
(``kept_partners``). NPCs (agents, NPC Corporations, factions) never count -
bounties and taxes would connect every ratter. A payment or contract counts
only if its own character was in the Alliance at the time (``tenure``).

The data is corptools' wallet journal and, for the contracts no ISK moved
with (a gift of items leaves no journal entry with the partner), its
contracts; without corptools there is none.

Each counterpart is then followed to its Corporation and Alliance
(``affiliations``); a hostile standing on any of the three makes it a hostile
partner, and the graph shows the chain up to the entity that carries it.
By default only hostile partners stay (``kept_partners``): sharing a trader
or a hauler outside the Alliance is everyday business in EVE, sharing a
hostile is not. A setting lets the neutral ones stay too, the blue never.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from django.apps import apps
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from .markers import character_audits

TRADING = "player_trading"
# corptools' Contract.availability of a contract offered to one party
PRIVATE = "personal"
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
    # private contracts with items; counted apart from the payments
    contracts: int = 0
    # "o": the own character gave (paid, issued), "i": it received; both may be there. Empty in an older snapshot
    direction: str = ""

    def add(self, day: str, trade: bool, isk, direction: str = "", contract: bool = False) -> None:
        if contract:
            self.contracts += 1
        else:
            self.payments += 1
            if trade:
                self.trades += 1
            self.isk += abs(isk or 0)
        self.direction = "".join(sorted(set(self.direction + direction)))
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
    # EVE IDs highlighted in the settings: red in the graph like a hostile, nothing else; shared as well
    highlights: frozenset = frozenset()
    # EVE ID -> the standing the Alliance itself holds, hostile or not; shared as well
    standings: dict = field(default_factory=dict)
    # own character ID -> birthday; read by ``fill_birthdays`` for the one page that shows the age
    birthdays: dict = field(default_factory=dict)

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

    @property
    def contracting(self) -> set:
        return {link.counterpart_id for link in self.links if link.contracts}

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
        return {
            "name": self._name(eve_id),
            "standing": hostile.standing if hostile else None,
            "held": self.standings.get(eve_id),
        }

    @property
    def rows(self) -> list[dict]:
        """One per link, for the table under the graph."""
        rows = []
        today = timezone.localdate()
        for link in self.links:
            entity = self.entities.get(link.counterpart_id)
            corporation_id = entity.corporation_id if entity else None
            alliance_id = entity.alliance_id if entity else None
            birthday = self.birthdays.get(link.character_id)
            rows.append(
                {
                    "character": self.characters.get(link.character_id, str(link.character_id)),
                    "character_id": link.character_id,
                    "birthday": birthday,
                    "age_days": (today - birthday).days if birthday else None,
                    "counterpart": self._name(link.counterpart_id),
                    "counterpart_id": link.counterpart_id,
                    "counterpart_held": self.standings.get(link.counterpart_id),
                    "hostile":self.reason(link.counterpart_id) is not None,
                    "corporation": self._group(corporation_id),
                    "alliance": self._group(alliance_id),
                    "payments": link.payments,
                    "trades": link.trades,
                    "contracts": link.contracts,
                    "isk": link.isk,
                    "first": link.first,
                    "last": link.last,
                }
            )
        return rows

    def _flagged(self, counterpart_id: int) -> int | None:
        """Like ``reason``, but a highlighted entity makes the chain red too; the graph only."""
        return next(
            (eve_id for eve_id in self.chain(counterpart_id) if eve_id in self.hostiles or eve_id in self.highlights),
            None,
        )

    def _node(self, eve_id, kind: str) -> dict:
        hostile = self.hostiles.get(eve_id)
        node = {
            "id": eve_id,
            "label": self._name(eve_id),
            # hostile_partner, hostile_corporation ...: the red tones in network.js
            "group": f"hostile_{kind}" if hostile or eve_id in self.highlights else kind,
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
            reason = self._flagged(counterpart_id)
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
                "kind": "trading" if link.trades else "payment" if link.payments else "contract",
                "payments": link.payments,
                "trades": link.trades,
                "contracts": link.contracts,
                "direction": link.direction,
                "first": link.first,
                "last": link.last,
            }
            for link in self.links
        ]
        return {"nodes": list(nodes.values()), "edges": edges}


ALLIANCE_KIND = "alliance"


def affiliate(accounts, hostiles: dict, more_ids=()) -> dict:
    """Look up the Corporation and Alliance of every counterpart and hand them to the accounts.

    ``hostiles`` maps the ID of every hostile contact to its Standing;
    ``more_ids`` are looked up along, in the same ESI requests. Returns the
    entities, which the snapshot stores once for all accounts.
    """
    from .affiliations import resolve

    accounts = list(accounts)
    entities = resolve(
        {counterpart_id for account in accounts for counterpart_id in account.counterparts} | set(more_ids)
    )
    for account in accounts:
        account.entities = entities
        account.hostiles = hostiles
    return entities


def kept_partners(accounts: dict, blues: set | None = None, inside=frozenset()) -> dict:
    """The accounts cut down to the partners that stay, by user ID; an account without one goes.

    Without ``blues`` only the hostile partners stay. With them the neutral
    ones too: a partner goes only when its chain holds a blue ID and no
    hostile one - a hostile anywhere in the chain wins (user, 2026-11-23).
    Needs the affiliations (``affiliate``) first: a partner is often hostile
    only through its Corporation or Alliance.

    A partner whose chain holds one of ``inside`` (the Alliance and its Corporations) goes in any case: a
    character Auth does not know, whose Corporation or Alliance ESI names as ours, is a member and no
    connection outside (user, 2026-11-23).
    """
    result = {}
    for user_id, account in accounts.items():
        if blues is None:
            kept = account.hostile
        else:
            kept = {
                counterpart_id
                for counterpart_id in account.counterparts
                if account.reason(counterpart_id) or blues.isdisjoint(account.chain(counterpart_id))
            }
        kept = {counterpart_id for counterpart_id in kept if inside.isdisjoint(account.chain(counterpart_id))}
        if not kept:
            continue
        account.links = [link for link in account.links if link.counterpart_id in kept]
        account.counterparts = {
            counterpart_id: name for counterpart_id, name in account.counterparts.items() if counterpart_id in kept
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


def connections(
    mains: dict,
    alliance_id: int,
    stats: dict | None = None,
    since=None,
    ignored_ref_types=(),
    characters=None,
    ignored_characters=(),
    ignored_counterparts=(),
    tenure=None,
) -> dict:
    """The accounts with connections outside the Alliance, by user ID.

    ``mains`` maps the user ID of every account to check to its main
    EveCharacter. ``stats`` gets the number of journal entries read. Only
    payments and contracts from ``since`` on count, and none of
    ``ignored_ref_types``, and none of ``ignored_characters`` (EVE IDs).
    With a ``tenure`` only those made while the own character was in the Alliance.
    ``ignored_counterparts`` (EVE IDs) are no connection at all: they count
    for neither the shared-partner rule nor player trading.
    ``characters`` is ``markers.Roster.characters`` when the caller has read
    the accounts' characters already.
    """
    if stats is not None:
        stats["journal_entries"] = 0
        stats["characters"] = 0
    if not mains or not apps.is_installed("corptools"):
        return {}
    from corptools.models import CharacterWalletJournalEntry, Contract, ContractItem

    if characters is None:
        characters = CharacterOwnership.objects.filter(user_id__in=mains).values_list(
            "user_id", "character__character_id", "character__character_name"
        )
    owner = {}
    names = {}
    for user_id, character_id, name, *_groups in characters:
        owner[character_id] = user_id
        names[character_id] = name
    if stats is not None:
        stats["characters"] = len(owner)
    inside = alliance_ids(alliance_id)
    # an ignored character stays in ``owner`` (a payment to it is still no connection outside) but is not read
    audits = character_audits([character_id for character_id in owner if character_id not in ignored_characters])

    # (user, own character, counterpart) -> link
    links = {}

    def add(character_id, party_ids, day: str, trade: bool, isk, direction: str = "", contract: bool = False) -> None:
        user_id = owner[character_id]
        for party_id in party_ids:
            # an own alt, a member of the Alliance or an NPC is no connection outside
            if (
                not party_id
                or party_id in inside
                or party_id in NPC_IDS
                or party_id in ignored_counterparts
                or owner.get(party_id) == user_id
            ):
                continue
            link = links.get((user_id, character_id, party_id))
            if link is None:
                link = links[(user_id, character_id, party_id)] = Link(character_id, party_id)
            link.add(day, trade, isk, direction, contract)

    entries = CharacterWalletJournalEntry.objects.filter(
        character_id__in=list(audits),
        ref_type__in=[ref_type for ref_type in PAYMENT_REF_TYPES if ref_type not in ignored_ref_types],
    )
    if since is not None:
        entries = entries.filter(date__gte=since)
    # no names here: most entries are payments inside the Alliance and drop out; _fill_names
    # looks up only the counterparts that stay
    entries = entries.values_list("character_id", "ref_type", "amount", "date", "first_party_id", "second_party_id")
    for audit_id, ref_type, amount, date, first_id, second_id in entries.iterator():
        if stats is not None:
            stats["journal_entries"] += 1
        # the journal is the own character's: a negative amount left its wallet
        direction = "i" if amount and amount > 0 else "o" if amount else ""
        own_id = audits[audit_id]
        if tenure is None or tenure.counts(own_id, date):
            add(own_id, (first_id, second_id), date.date().isoformat(), ref_type == TRADING, amount, direction)

    # A private contract with items is a kind of its own, with or without ISK (user, 2026-11-23). Any other
    # contract with ISK is in the journal already; without any - collateral included, which has its own
    # journal entries - it is a payment of 0 ISK. Every type and status, both directions (user)
    has_items = Exists(ContractItem.objects.filter(contract=OuterRef("pk")))
    contracts = Contract.objects.filter(character_id__in=list(audits)).annotate(has_items=has_items)
    if since is not None:
        contracts = contracts.filter(date_issued__gte=since)
    for audit_id, date, price, reward, collateral, availability, with_items, issuer_id, *party_ids in contracts.values_list(
        "character_id",
        "date_issued",
        "price",
        "reward",
        "collateral",
        "availability",
        "has_items",
        "issuer_id",
        "assignee_id",
        "acceptor_id",
    ).iterator():
        own_id = audits[audit_id]
        if tenure is not None and not tenure.counts(own_id, date):
            continue
        parties = {issuer_id, *party_ids}
        day = date.date().isoformat()
        if availability == PRIVATE and with_items:
            add(own_id, parties, day, False, 0, "o" if issuer_id == own_id else "i", contract=True)
        elif not (price or reward or collateral):
            add(own_id, parties, day, False, 0)

    by_user = defaultdict(list)
    for (user_id, _character_id, _counterpart_id), link in links.items():
        by_user[user_id].append(link)

    result = {}
    for user_id, user_links in by_user.items():
        main = mains[user_id]
        account = Connections(user_id, main.character_id, main.character_name, main.corporation_id)
        account.links = user_links
        keep = account.shared | account.trading | account.contracting
        if not keep:
            continue
        account.links = sorted(
            (link for link in user_links if link.counterpart_id in keep),
            key=lambda link: (-link.payments, link.character_id, link.counterpart_id),
        )
        account.characters = {
            character_id: name for character_id, name in names.items() if owner[character_id] == user_id
        }
        account.counterparts = dict.fromkeys(keep)
        result[user_id] = account

    _fill_names([account.counterparts for account in result.values()])
    return result


def fill_birthdays(accounts) -> None:
    """Hand each account the birthdays of its characters: one query, for the page that shows the age.

    Auth has no birthday for a character it never refreshed from ESI; the table shows a dash then.
    """
    accounts = list(accounts)
    ids = {link.character_id for account in accounts for link in account.links}
    found = dict(
        EveCharacter.objects.filter(character_id__in=ids, birthday__isnull=False).values_list(
            "character_id", "birthday"
        )
    )
    for account in accounts:
        account.birthdays = found


def _fill_names(tables: list[dict]) -> None:
    """The counterparts' names, from Auth's tables and corptools' names; else the ID."""
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
