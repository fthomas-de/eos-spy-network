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
    def rows(self) -> list[tuple]:
        """(own character, counterpart, payments, trades, ISK) per link, for the table under the graph."""
        return [
            (
                self.characters.get(link.character_id, str(link.character_id)),
                self.counterparts.get(link.counterpart_id, str(link.counterpart_id)),
                link.payments,
                link.trades,
                link.isk,
            )
            for link in self.links
        ]

    def graph(self) -> dict:
        """Nodes and edges for network.js; groups name the colours there."""
        linked = {link.character_id for link in self.links}
        shared = self.shared
        nodes = [
            {
                "id": character_id,
                "label": name,
                "group": "main" if character_id == self.main_id else "alt",
            }
            for character_id, name in self.characters.items()
            # an alt without a link would float alone; the main stays as the anchor
            if character_id in linked or character_id == self.main_id
        ]
        nodes += [
            {
                "id": counterpart_id,
                "label": name,
                # a shared partner stays one even when it also traded
                "group": "shared" if counterpart_id in shared else "trading",
            }
            for counterpart_id, name in self.counterparts.items()
        ]
        edges = [
            {
                "from": link.character_id,
                "to": link.counterpart_id,
                "payments": link.payments,
                "trades": link.trades,
            }
            for link in self.links
        ]
        return {"nodes": nodes, "edges": edges}


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
        "first_party_id",
        "first_party_name__name",
        "second_party_id",
        "second_party_name__name",
    )
    for character_id, ref_type, amount, first_id, first_name, second_id, second_name in entries.iterator():
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
            link.payments += 1
            if ref_type == TRADING:
                link.trades += 1
            link.isk += abs(amount or 0)
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
