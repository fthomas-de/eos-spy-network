"""Suspicious markers per account, and the Corporations of the Alliance they are shown in.

An account is a main with all its characters: a spy keeps the contact on an
alt, rarely on the main. Each marker counts what it found and names the
hostiles behind it. The data is corptools' - an account without a working
Character Audit simply shows fewer markers; corptools is optional, without
it only the current Corporation and Alliance are checked.

A hostile is what ``hostiles.hostile_index()`` says, so a character Auth has
never seen counts only when it is a contact itself: mails, ISK and contracts
with unknown characters of a hostile Corporation stay unseen.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from django.apps import apps
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from allianceauth.authentication.models import CharacterOwnership, UserProfile
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from .hostiles import HostileIndex, hostile_index
from .models import SpyConfiguration

MEMBERSHIP = "membership"
CORP_CHANGES = "corp_changes"
CONTACTS = "contacts"
MAILS = "mails"
WALLET = "wallet"
CONTRACTS = "contracts"

# in this order on the pages
KINDS = (MEMBERSHIP, CORP_CHANGES, CONTACTS, MAILS, WALLET, CONTRACTS)

LABELS = {
    MEMBERSHIP: _("Hostile membership"),
    CORP_CHANGES: _("Frequent Corporation changes"),
    CONTACTS: _("Friendly to hostiles"),
    MAILS: _("Mails with hostiles"),
    WALLET: _("ISK with hostiles"),
    CONTRACTS: _("Contracts with hostiles"),
}

DESCRIPTIONS = {
    MEMBERSHIP: _("A character is or was in a hostile Corporation or Alliance."),
    CORP_CHANGES: _("A character joined many Corporations within the last 365 days."),
    CONTACTS: _("A character's own contacts hold a hostile with a positive standing or on the watch list."),
    MAILS: _("Mails from or to hostiles."),
    WALLET: _("Wallet journal entries with hostiles."),
    CONTRACTS: _("Contracts with hostiles."),
}

# whose details are evidence: only shown with view_evidence
EVIDENCE = {MAILS, WALLET, CONTRACTS}

CORPTOOLS = "corptools"


@dataclass
class Marker:
    kind: str
    # what was found: journal entries, mails, contracts, contacts, Corporations joined
    count: int = 0
    details: set = field(default_factory=set)
    # the details as a table, JSON-ready: per own character and hostile for ISK and contracts,
    # per character with the Corporations joined for the Corporation changes
    rows: list = field(default_factory=list)

    @property
    def label(self):
        return LABELS[self.kind]

    @property
    def description(self):
        return DESCRIPTIONS[self.kind]

    @property
    def is_evidence(self) -> bool:
        return self.kind in EVIDENCE

    @property
    def sorted_details(self) -> list[str]:
        return sorted(self.details, key=str.lower)

    @property
    def dealings(self) -> bool:
        """ISK and contracts show their rows as a table."""
        return self.kind in (WALLET, CONTRACTS) and bool(self.rows)

    @property
    def joins(self) -> bool:
        """Corporation changes name the Corporations in a tooltip per character."""
        return self.kind == CORP_CHANGES and bool(self.rows)


@dataclass
class Dealings:
    """What one own character did with one hostile: how often, how much, when, in which way."""

    count: int = 0
    isk: Decimal = Decimal(0)
    first: datetime | None = None
    last: datetime | None = None
    types: set = field(default_factory=set)

    def add(self, when: datetime, kind: str, isk=None) -> None:
        self.count += 1
        self.isk += abs(isk or 0)
        self.first = when if self.first is None else min(self.first, when)
        self.last = when if self.last is None else max(self.last, when)
        self.types.add(kind.replace("_", " "))

    def row(self, character: str, counterpart: str) -> dict:
        return {
            "character": character,
            "counterpart": counterpart,
            "count": self.count,
            "isk": str(self.isk),
            "first": self.first.date().isoformat(),
            "last": self.last.date().isoformat(),
            "types": sorted(self.types),
        }


@dataclass
class Suspect:
    user_id: int
    main: EveCharacter
    character_count: int
    markers: dict = field(default_factory=dict)

    def mark(self, kind: str, detail: str, count: int = 1) -> None:
        marker = self.markers.setdefault(kind, Marker(kind))
        marker.count += count
        marker.details.add(detail)

    @property
    def marker_list(self) -> list[Marker]:
        return [self.markers[kind] for kind in KINDS if kind in self.markers]


@dataclass
class CorporationTile:
    id: int
    name: str
    ticker: str
    mains: int = 0
    # only accounts with at least one marker, the most marked first
    suspects: list = field(default_factory=list)

    def counts(self) -> list[tuple]:
        """(marker label, description, number of suspects with it) for every marker found."""
        found = defaultdict(int)
        for suspect in self.suspects:
            for kind in suspect.markers:
                found[kind] += 1
        return [(LABELS[kind], DESCRIPTIONS[kind], found[kind]) for kind in KINDS if kind in found]


def corptools_installed() -> bool:
    return apps.is_installed(CORPTOOLS)


def _no_step(_name: str) -> None:
    pass


def corporation_tiles(
    config: SpyConfiguration | None = None, corporation_id: int | None = None, step=_no_step
) -> list:
    """The Corporations of the configured Alliance, each with its marked accounts; with
    ``corporation_id`` only that one. ``step`` is told the name of each check as it starts."""
    config = config or SpyConfiguration.get_solo()
    if not config.alliance:
        return []
    corporations = EveCorporationInfo.objects.filter(alliance=config.alliance).order_by("corporation_name")
    if corporation_id is not None:
        corporations = corporations.filter(corporation_id=corporation_id)
    tiles = {
        corporation.corporation_id: CorporationTile(
            corporation.corporation_id, corporation.corporation_name, corporation.corporation_ticker
        )
        for corporation in corporations
    }
    if not tiles:
        return []

    accounts = {}
    for profile in UserProfile.objects.filter(main_character__corporation_id__in=tiles).select_related(
        "main_character"
    ):
        accounts[profile.user_id] = Suspect(profile.user_id, profile.main_character, 0)
        tiles[profile.main_character.corporation_id].mains += 1

    step("hostiles")
    index = hostile_index(config)
    if accounts and index:
        _check(accounts, index, config, step)

    for suspect in accounts.values():
        if suspect.markers:
            tiles[suspect.main.corporation_id].suspects.append(suspect)
    for tile in tiles.values():
        tile.suspects.sort(key=lambda suspect: (-len(suspect.markers), suspect.main.character_name.lower()))
    return list(tiles.values())


def _check(accounts: dict, index: HostileIndex, config: SpyConfiguration, step=_no_step) -> None:
    step("membership")
    # EVE ID of every character -> its account; a character of the own account is never a counterpart
    owner = {}
    names = {}
    for user_id, character_id, name, corporation_id, alliance_id in CharacterOwnership.objects.filter(
        user_id__in=accounts
    ).values_list(
        "user_id",
        "character__character_id",
        "character__character_name",
        "character__corporation_id",
        "character__alliance_id",
    ):
        owner[character_id] = user_id
        names[character_id] = name
        accounts[user_id].character_count += 1
        for group_id in (corporation_id, alliance_id):
            if group_id in index:
                accounts[user_id].mark(MEMBERSHIP, f"{name}: {index.describe(group_id)}")
                break

    if not corptools_installed():
        return

    own = defaultdict(set)
    for character_id, user_id in owner.items():
        own[user_id].add(character_id)

    def counterparts(user_id, *party_ids):
        return {party_id for party_id in party_ids if party_id in index and party_id not in own[user_id]}

    characters = list(owner)
    hostile_ids = index.ids
    step("history")
    _check_history(accounts, index, config, owner, names, characters)
    step("contacts")
    _check_contacts(accounts, index, owner, names, characters, hostile_ids)
    step("mails")
    _check_mails(accounts, index, owner, characters, hostile_ids, counterparts)
    step("wallet")
    _check_wallet(accounts, index, owner, names, characters, hostile_ids, counterparts)
    step("contracts")
    _check_contracts(accounts, index, owner, names, characters, hostile_ids, counterparts)


def _check_history(accounts, index, config, owner, names, characters):
    from corptools.models import CorporationHistory

    since = timezone.now() - timedelta(days=365)
    joined = defaultdict(list)  # character -> [(start date, Corporation name)]
    for character_id, corporation_id, corporation_name, start_date in CorporationHistory.objects.filter(
        character__character__character_id__in=characters
    ).values_list("character__character__character_id", "corporation_id", "corporation_name__name", "start_date"):
        if corporation_id in index:
            accounts[owner[character_id]].mark(MEMBERSHIP, f"{names[character_id]}: {index.describe(corporation_id)}")
        if start_date >= since:
            joined[character_id].append((start_date, corporation_name or str(corporation_id)))
    for character_id, corporations in joined.items():
        count = len(corporations)
        if count >= config.corp_changes_per_year:
            suspect = accounts[owner[character_id]]
            suspect.mark(CORP_CHANGES, f"{names[character_id]}: {count}", count)
            suspect.markers[CORP_CHANGES].rows.append(
                {
                    "character": names[character_id],
                    "count": count,
                    "corporations": [[start.date().isoformat(), name] for start, name in sorted(corporations)],
                }
            )


def _check_contacts(accounts, index, owner, names, characters, hostile_ids):
    from corptools.models import CharacterContact

    for character_id, contact_id, standing in CharacterContact.objects.filter(
        Q(standing__gt=0) | Q(watched=True),
        character__character__character_id__in=characters,
        contact_id__in=hostile_ids,
    ).values_list("character__character__character_id", "contact_id", "standing"):
        accounts[owner[character_id]].mark(
            # normalize: 5, not the column's 5.00
            CONTACTS,
            f"{names[character_id]}: {index.describe(contact_id)} ({standing.normalize():f})",
        )


def _check_mails(accounts, index, owner, characters, hostile_ids, counterparts):
    from corptools.models import MailMessage

    found = defaultdict(set)  # (account, mail ID) -> hostile counterparts
    for character_id, mail_id, from_id in MailMessage.objects.filter(
        character__character__character_id__in=characters, from_id__in=hostile_ids
    ).values_list("character__character__character_id", "mail_id", "from_id"):
        user_id = owner[character_id]
        found[(user_id, mail_id)] |= counterparts(user_id, from_id)
    for character_id, mail_id, recipient_id in MailMessage.recipients.through.objects.filter(
        mailmessage__character__character__character_id__in=characters,
        mailrecipient_id__in=hostile_ids,
    ).values_list("mailmessage__character__character__character_id", "mailmessage__mail_id", "mailrecipient_id"):
        user_id = owner[character_id]
        found[(user_id, mail_id)] |= counterparts(user_id, recipient_id)
    # a mail in the boxes of two own characters counts once
    _mark_found(accounts, index, found, MAILS)


def _check_wallet(accounts, index, owner, names, characters, hostile_ids, counterparts):
    from corptools.models import CharacterWalletJournalEntry

    found = defaultdict(set)
    dealings = defaultdict(Dealings)  # (account, own character, hostile) -> Dealings
    for pk, character_id, first_party_id, second_party_id, date, ref_type, amount in (
        CharacterWalletJournalEntry.objects.filter(
            Q(first_party_id__in=hostile_ids) | Q(second_party_id__in=hostile_ids),
            character__character__character_id__in=characters,
        ).values_list(
            "pk", "character__character__character_id", "first_party_id", "second_party_id", "date", "ref_type", "amount"
        )
    ):
        user_id = owner[character_id]
        parties = counterparts(user_id, first_party_id, second_party_id)
        found[(user_id, pk)] |= parties
        for party_id in parties:
            dealings[(user_id, character_id, party_id)].add(date, ref_type, amount)
    _mark_found(accounts, index, found, WALLET)
    _add_rows(accounts, index, names, dealings, WALLET)


def _check_contracts(accounts, index, owner, names, characters, hostile_ids, counterparts):
    from corptools.models import Contract

    found = defaultdict(set)
    dealings = defaultdict(Dealings)
    for (
        character_id,
        contract_id,
        issuer_id,
        issuer_corporation_id,
        assignee_id,
        acceptor_id,
        date_issued,
        contract_type,
    ) in Contract.objects.filter(
        Q(issuer_id__in=hostile_ids)
        | Q(issuer_corporation_id__in=hostile_ids)
        | Q(assignee_id__in=hostile_ids)
        | Q(acceptor_id__in=hostile_ids),
        character__character__character_id__in=characters,
    ).values_list(
        "character__character__character_id",
        "contract_id",
        "issuer_id",
        "issuer_corporation_id",
        "assignee_id",
        "acceptor_id",
        "date_issued",
        "contract_type",
    ):
        user_id = owner[character_id]
        parties = [issuer_id, assignee_id, acceptor_id]
        # the issuer's Corporation speaks for a stranger only: an own alt's Corporation is the membership marker
        if owner.get(issuer_id) != user_id:
            parties.append(issuer_corporation_id)
        parties = counterparts(user_id, *parties)
        found[(user_id, contract_id)] |= parties
        for party_id in parties:
            dealings[(user_id, character_id, party_id)].add(date_issued, contract_type)
    _mark_found(accounts, index, found, CONTRACTS)
    _add_rows(accounts, index, names, dealings, CONTRACTS)


def _mark_found(accounts, index, found, kind):
    for (user_id, _item), party_ids in found.items():
        if not party_ids:
            continue
        marker = accounts[user_id].markers.setdefault(kind, Marker(kind))
        marker.count += 1
        marker.details.update(index.describe(party_id) for party_id in party_ids)


def _add_rows(accounts, index, names, dealings, kind):
    """One row per own character and hostile, the latest first."""
    for (user_id, character_id, party_id), dealing in sorted(
        dealings.items(), key=lambda item: item[1].last, reverse=True
    ):
        accounts[user_id].markers[kind].rows.append(dealing.row(names[character_id], index.describe(party_id)))
