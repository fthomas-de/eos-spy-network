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
from django.db import connection
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from allianceauth.authentication.models import CharacterOwnership, OwnershipRecord, UserProfile
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from . import killmails
from .hostiles import HostileIndex, blue_entities, hostile_index
from .models import BlueKill, CapitalContractItem, SpyConfiguration

MEMBERSHIP = "membership"
CORP_CHANGES = "corp_changes"
OWNER_CHANGES = "owner_changes"
CONTACTS = "contacts"
MAILS = "mails"
WALLET = "wallet"
CONTRACTS = "contracts"
CAPITAL_CONTRACTS = "capital_contracts"
BLUE_KILLS = "blue_kills"

# in this order on the pages
KINDS = (MEMBERSHIP, CORP_CHANGES, OWNER_CHANGES, CONTACTS, MAILS, WALLET, CONTRACTS, CAPITAL_CONTRACTS, BLUE_KILLS)

LABELS = {
    MEMBERSHIP: _("Hostile membership"),
    CORP_CHANGES: _("Frequent Corporation changes"),
    OWNER_CHANGES: _("Owner changes"),
    CONTACTS: _("Friendly to hostiles"),
    MAILS: _("Mails with hostiles"),
    WALLET: _("ISK with hostiles"),
    CONTRACTS: _("Contracts with hostiles"),
    CAPITAL_CONTRACTS: _("Capital in contract"),
    BLUE_KILLS: _("Blue kills"),
}

DESCRIPTIONS = {
    MEMBERSHIP: _("A character is or was in a hostile Corporation or Alliance."),
    CORP_CHANGES: _("A character joined many Corporations within the last 365 days."),
    OWNER_CHANGES: _("A character changed hands: Alliance Auth holds an earlier owner of it."),
    CONTACTS: _(
        "A character's own contacts hold a hostile with a positive standing."
    ),
    MAILS: _("Mails from or to hostiles."),
    WALLET: _("Wallet journal entries with hostiles."),
    CONTRACTS: _("Contracts with hostiles."),
    CAPITAL_CONTRACTS: _("A character offers a capital ship in an open public contract."),
    BLUE_KILLS: _("A character was on a killmail whose victim is in the Alliance (awox) or blue to it."),
}

CORPTOOLS = "corptools"

# the kind of a mail in the rows: from the hostile, or to it
RECEIVED = "received"
SENT = "sent"

# wallet entries that pay for a contract: corptools' journal names the contract in context_id
CONTRACT_REF_TYPES = (
    "contract_price",
    "contract_price_payment_corp",
    "contract_reward",
    "contract_collateral",
    "contract_collateral_payout",
)
# corptools' Contract.availability of a contract anybody in the region may take: whoever does is a stranger on
# the market, so neither the contract nor its wallet entries count, in the markers or the Network (user, 2026-11-24)
PUBLIC = "public"


def without_public_contracts(entries):
    """The wallet entries less those that pay for a public contract corptools holds, of any time."""
    from corptools.models import Contract

    return entries.exclude(
        context_id_type="contract_id",
        context_id__in=Contract.objects.filter(availability=PUBLIC).values("contract_id"),
    )


@dataclass
class Marker:
    kind: str
    # what was found: journal entries, mails, contracts, contacts, Corporations joined
    count: int = 0
    details: set = field(default_factory=set)
    # the details as a table, JSON-ready: per own character and hostile for ISK and contracts,
    # per character with the Corporations joined for the Corporation changes
    rows: list = field(default_factory=list)
    # EVE IDs of the account's own characters behind the finding: other apps (api.py) show a marker
    # at the character, in its own Corporation, not only at the main
    character_ids: set = field(default_factory=set)

    @property
    def label(self):
        return LABELS[self.kind]

    @property
    def description(self):
        return DESCRIPTIONS[self.kind]

    @property
    def sorted_details(self) -> list[str]:
        return sorted(self.details, key=str.lower)

    @property
    def dealings(self) -> bool:
        """ISK, contracts and mails show their rows as a table; mails of a snapshot of 0.1.5 or older have none."""
        return self.kind in (WALLET, CONTRACTS, MAILS) and bool(self.rows)

    @property
    def affiliated(self) -> bool:
        """The rows name the counterpart's Corporation and Alliance; a snapshot of 0.0.5 (contacts: 0.0.16) or older does not."""
        return (self.dealings or self.contacts) and "alliance" in self.rows[0]

    @property
    def joins(self) -> bool:
        """Corporation changes name the Corporations in a tooltip per character."""
        return self.kind == CORP_CHANGES and bool(self.rows)

    @property
    def owners(self) -> bool:
        """Owner changes show one case per character with its earlier owners; the table is the Corporation changes'."""
        return self.kind == OWNER_CHANGES and bool(self.rows)

    @property
    def kills(self) -> bool:
        """Blue kills show their killmails as a table."""
        return self.kind == BLUE_KILLS and bool(self.rows)

    @property
    def capitals(self) -> bool:
        """Capital contracts show one row per contract."""
        return self.kind == CAPITAL_CONTRACTS and bool(self.rows)

    @property
    def contacts(self) -> bool:
        """Friendly hostile contacts show one row per contact and standing, with note and tick."""
        return self.kind == CONTACTS and bool(self.rows)

    @property
    def memberships(self) -> bool:
        """Hostile memberships show one row per hostile group, with note and tick; a snapshot of 0.1.5 or older has
        no rows."""
        return self.kind == MEMBERSHIP and bool(self.rows)

    @property
    def cleared_rows(self) -> list:
        """The reviewed rows ticked off: folded under the open ones (user, 2026-11-27)."""
        return [row for row in self.rows if row.get("cleared")]


def million(isk) -> float | None:
    """ISK in million, as the minimum kill value is set (user); None stays unknown."""
    return None if isk is None else float(isk) / 1_000_000


@dataclass
class Dealings:
    """What one own character did with one hostile: how often, how much, when, in which way."""

    count: int = 0
    isk: Decimal = Decimal(0)
    first: datetime | None = None
    last: datetime | None = None
    types: set = field(default_factory=set)
    # one of the entries pays for a contract: the row gets the popup button
    contract_payments: bool = False
    # [journal entry, contract or mail ID, date, kind, ISK, subject] each: the details behind the sums, and what a
    # review covers; the subject is a mail's only, None otherwise
    items: list = field(default_factory=list)

    def add(self, item_id: int, when: datetime | None, kind: str, isk=None, subject=None) -> None:
        self.count += 1
        self.contract_payments = self.contract_payments or kind in CONTRACT_REF_TYPES
        self.isk += abs(isk or 0)
        # corptools allows a mail without a timestamp: it counts, undated
        if when is not None:
            self.first = when if self.first is None else min(self.first, when)
            self.last = when if self.last is None else max(self.last, when)
        self.types.add(kind.replace("_", " "))
        day = when.date().isoformat() if when else ""
        self.items.append([item_id, day, kind, str(abs(isk or 0)), subject])

    def row(self, character: str, character_id: int, counterpart_id: int, counterpart: str) -> dict:
        return {
            "character": character,
            # the popup of a contract payment looks the contracts up by this ID and the counterpart's
            "character_id": character_id,
            # the snapshot adds the counterpart's Corporation and Alliance by this ID
            "counterpart_id": counterpart_id,
            "counterpart": counterpart,
            "count": self.count,
            "isk": str(self.isk),
            "million": million(self.isk),
            "first": self.first.date().isoformat() if self.first else "",
            "last": self.last.date().isoformat() if self.last else "",
            "types": sorted(self.types),
            "contract_payments": self.contract_payments,
            "items": sorted(self.items, key=lambda item: (item[1], item[0]), reverse=True),
        }


@dataclass
class Suspect:
    user_id: int
    main: EveCharacter
    character_count: int
    markers: dict = field(default_factory=dict)

    def mark(self, kind: str, detail: str, character_id: int, count: int = 1) -> None:
        marker = self.markers.setdefault(kind, Marker(kind))
        marker.count += count
        marker.details.add(detail)
        marker.character_ids.add(character_id)

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
    # mains whose every finding is cleared, by name: {"main": ..., "rows": [...]}; filled by snapshot.Report
    cleared: list = field(default_factory=list)
    # marked accounts whose main is elsewhere, with an alt here: the most marked first
    visitors: list = field(default_factory=list)

    def counts(self) -> list[tuple]:
        """(marker label, description, number of suspects with it) for every marker found."""
        found = defaultdict(int)
        for suspect in self.suspects:
            for kind in suspect.markers:
                found[kind] += 1
        return [(LABELS[kind], DESCRIPTIONS[kind], found[kind]) for kind in KINDS if kind in found]


@dataclass
class Visitor:
    """A marked account seen from a Corporation it has an alt in, its main being elsewhere (user, 2026-11-19):
    its CEO is answerable for that alt, so the whole account shows there too, read only."""

    suspect: Suspect
    alts: list  # (EVE ID, name) of the account's characters in this Corporation
    # the main's Corporation has a page of this app; snapshot.Report sets it
    page: bool = False


def by_markers(suspect: Suspect) -> tuple:
    """The most marked first, then by name."""
    return (-len(suspect.markers), suspect.main.character_name.lower())


def corptools_installed() -> bool:
    return apps.is_installed(CORPTOOLS)


def _no_step(_name: str) -> None:
    pass


@dataclass
class Roster:
    """The Corporations of the Alliance and their accounts; read once per run, the network uses it as well."""

    corporations: list  # EveCorporationInfo, by name
    mains: dict  # user ID -> main EveCharacter
    # (user ID, EVE ID, name, Corporation ID, Alliance ID) of every character of these accounts
    characters: list


def roster(config: SpyConfiguration, corporation_id: int | None = None) -> Roster:
    corporations = EveCorporationInfo.objects.filter(alliance=config.alliance).order_by("corporation_name")
    if corporation_id is not None:
        corporations = corporations.filter(corporation_id=corporation_id)
    corporations = list(corporations)
    corporation_ids = [corporation.corporation_id for corporation in corporations]
    # a player is all of his characters: one with only an alt here, the main outside the Alliance, counts too
    visiting = CharacterOwnership.objects.filter(character__corporation_id__in=corporation_ids).values("user_id")
    mains = {
        profile.user_id: profile.main_character
        for profile in UserProfile.objects.filter(
            Q(main_character__corporation_id__in=corporation_ids) | Q(user_id__in=visiting),
            main_character__isnull=False,
        ).select_related("main_character")
    }
    characters = list(
        CharacterOwnership.objects.filter(user_id__in=mains).values_list(
            "user_id",
            "character__character_id",
            "character__character_name",
            "character__corporation_id",
            "character__alliance_id",
        )
    )
    return Roster(corporations, mains, characters)


def character_audits(character_ids) -> dict[int, int]:
    """corptools' CharacterAudit ID -> EVE ID of the character.

    corptools' tables point at the audit. Filtering on it directly lets a
    query range over the (character, date) indexes; filtering on the EVE ID
    joins the audit and EveCharacter for every row and leaves MySQL to guess
    the join order.
    """
    from corptools.models import CharacterAudit

    return dict(
        CharacterAudit.objects.filter(character__character_id__in=character_ids).values_list(
            "pk", "character__character_id"
        )
    )


def corporation_tiles(
    config: SpyConfiguration | None = None,
    corporation_id: int | None = None,
    step=_no_step,
    hostiles: list | None = None,
    members: Roster | None = None,
    tenure=None,
) -> list:
    """The Corporations of the configured Alliance, each with its marked accounts; with
    ``corporation_id`` only that one. ``step`` is told the name of each check as it starts.
    ``hostiles`` (``hostile_entities``) and ``members`` (``roster``) save reading them twice. With a
    ``tenure`` (``tenure.load``) mails, ISK, contracts and kills count only from the time the character was in
    the Alliance."""
    config = config or SpyConfiguration.get_solo()
    if not config.alliance:
        return []
    members = members or roster(config, corporation_id)
    tiles = {
        corporation.corporation_id: CorporationTile(
            corporation.corporation_id, corporation.corporation_name, corporation.corporation_ticker
        )
        for corporation in members.corporations
    }
    if not tiles:
        return []

    accounts = {}
    for user_id, main in members.mains.items():
        accounts[user_id] = Suspect(user_id, main, 0)
        # a main outside the Alliance (or the one Corporation asked for) has no tile, only its alts' visits
        if main.corporation_id in tiles:
            tiles[main.corporation_id].mains += 1

    step("hostiles")
    index = hostile_index(config, hostiles)
    if accounts and index:
        _check(accounts, index, config, members.characters, step, tenure)
    # blue kills need no hostile: the victim is a friend
    if accounts:
        step("kills")
        _check_kills(accounts, config, members.characters, tenure)
    # like the kills, no hostile needed: the earlier owner itself is the finding
    if accounts:
        _check_owner_changes(accounts, members.characters)
    # like the kills, no hostile needed: the contract itself is the finding
    if accounts:
        step("capitals")
        _check_capital_contracts(accounts, config, members.characters)

    for suspect in accounts.values():
        if suspect.markers and suspect.main.corporation_id in tiles:
            tiles[suspect.main.corporation_id].suspects.append(suspect)
    alts = defaultdict(list)  # (Corporation, user) -> the account's characters there
    for user_id, character_id, name, corporation_id, _alliance_id in members.characters:
        if corporation_id in tiles and corporation_id != accounts[user_id].main.corporation_id:
            alts[(corporation_id, user_id)].append((character_id, name))
    for (corporation_id, user_id), named in alts.items():
        if accounts[user_id].markers:
            named.sort(key=lambda alt: alt[1].lower())
            tiles[corporation_id].visitors.append(Visitor(accounts[user_id], named))
    for tile in tiles.values():
        tile.suspects.sort(key=by_markers)
        tile.visitors.sort(key=lambda visitor: by_markers(visitor.suspect))
    return list(tiles.values())


def _check(
    accounts: dict, index: HostileIndex, config: SpyConfiguration, characters: list, step=_no_step, tenure=None
) -> None:
    step("membership")
    # EVE ID of every character -> its account; a character of the own account is never a counterpart
    owner = {}
    names = {}
    current = set()  # (character, Corporation or Alliance) marked as a membership of today
    for user_id, character_id, name, corporation_id, alliance_id in characters:
        owner[character_id] = user_id
        names[character_id] = name
        accounts[user_id].character_count += 1
        for group_id in (corporation_id, alliance_id):
            if group_id in index:
                accounts[user_id].mark(MEMBERSHIP, f"{name}: {index.describe(group_id)}", character_id)
                current.add((character_id, group_id))
                # Auth knows no start: the history record takes this item over when corptools has one
                _add_membership(accounts[user_id], index, group_id, character_id, name, f"{character_id}:auth", "")
                break

    if not corptools_installed():
        return

    own = defaultdict(set)
    for character_id, user_id in owner.items():
        own[user_id].add(character_id)

    def counterparts(user_id, when, *party_ids):
        # a hostile of today that was in the Alliance at the time was a member then (user, 2026-11-24)
        return {
            party_id
            for party_id in party_ids
            if party_id in index
            and party_id not in own[user_id]
            and not (tenure is not None and tenure.was_ours(party_id, when))
        }

    # ignored with the button: no ISK or contract counterpart, but still one of the mails (user)
    ignored = {int(eve_id) for eve_id in config.ignored_network_counterparts or ()}

    def dealing_counterparts(user_id, when, *party_ids):
        return counterparts(user_id, when, *party_ids) - ignored

    audits = character_audits(list(owner))
    hostile_ids = index.ids
    # the hostile list is today's: the further back, the likelier a hostile was a friend then
    since = config.since()
    step("history")
    _check_history(accounts, index, config, owner, names, audits, since, current)
    step("contacts")
    # contacts carry no date in corptools: today's are checked whatever the time frame
    ignored_characters = set(config.ignored_contact_characters or ())
    contact_audits = {
        audit_id: character_id for audit_id, character_id in audits.items() if character_id not in ignored_characters
    }
    _check_contacts(accounts, index, owner, names, contact_audits, hostile_ids)
    step("mails")
    _check_mails(accounts, index, owner, names, audits, hostile_ids, counterparts, since, tenure)
    step("wallet")
    _check_wallet(
        accounts, index, owner, names, audits, hostile_ids, dealing_counterparts, since, config.ignored_ref_types or (),
        tenure,
    )
    step("contracts")
    _check_contracts(accounts, index, owner, names, audits, hostile_ids, dealing_counterparts, since, tenure)


def _check_history(accounts, index, config, owner, names, audits, since=None, current=frozenset()):
    from corptools.models import CorporationHistory

    year_ago = timezone.now() - timedelta(days=365)
    records = defaultdict(list)  # character -> [(start date, Corporation ID, Corporation name, ESI record ID)]
    for audit_id, corporation_id, corporation_name, start_date, record_id in CorporationHistory.objects.filter(
        character_id__in=list(audits)
    ).values_list("character_id", "corporation_id", "corporation_name__name", "start_date", "record_id"):
        records[audits[audit_id]].append(
            (start_date, corporation_id, corporation_name or str(corporation_id), record_id)
        )

    joined = defaultdict(list)  # character -> [(start date, Corporation name, ESI record ID)]
    for character_id, history in records.items():
        history.sort()
        # a membership ends where the next one starts; the last one lasts until today
        ends = [following[0] for following in history[1:]] + [None]
        for (start_date, corporation_id, corporation_name, record_id), end_date in zip(history, ends):
            suspect = accounts[owner[character_id]]
            item_id = f"{character_id}:{record_id}"
            if end_date is None and (character_id, corporation_id) in current:
                # the open-ended record is today's membership, marked already: one fact, not two findings - its
                # record names it from now on, so leaving the Corporation later keeps the same item
                for row in suspect.markers[MEMBERSHIP].rows:
                    for item in row["items"]:
                        if item[0] == f"{character_id}:auth" and row["group_id"] == corporation_id:
                            item[0], item[1] = item_id, start_date.date().isoformat()
            elif corporation_id in index and (since is None or end_date is None or end_date >= since):
                suspect.mark(MEMBERSHIP, f"{names[character_id]}: {index.describe(corporation_id)}", character_id)
                _add_membership(
                    suspect, index, corporation_id, character_id, names[character_id], item_id,
                    start_date.date().isoformat(),
                )
            if start_date >= year_ago:
                joined[character_id].append((start_date, corporation_name, record_id))
    for character_id, corporations in joined.items():
        count = len(corporations)
        if count >= config.corp_changes_per_year:
            suspect = accounts[owner[character_id]]
            suspect.mark(CORP_CHANGES, f"{names[character_id]}: {count}", character_id, count)
            corporations.sort()
            suspect.markers[CORP_CHANGES].rows.append(
                {
                    "character": names[character_id],
                    "character_id": character_id,
                    "count": count,
                    "corporations": [[start.date().isoformat(), name] for start, name, _record in corporations],
                    # [ESI record ID, day, Corporation] each, the latest first: what a review covers
                    "items": [
                        [record_id, start.date().isoformat(), name] for start, name, record_id in reversed(corporations)
                    ],
                }
            )


def _check_owner_changes(accounts, characters):
    """Characters that changed hands (user, 2026-11-27): Alliance Auth keeps an ``OwnershipRecord`` per owner hash
    of a character, and a record whose hash is not the one it holds today is an earlier owner. Only the hash
    counts: the same player moving the character to another Auth account keeps it. A record has no end, and
    ``created`` is the day Auth first saw that owner, not when the character was sold.

    shortcut: the whole history, whatever the time frame - ``created`` is ``auto_now``, no date to cut by; upgrade
    when someone asks. A record goes with its user (cascade): an earlier owner's deleted account takes the finding.
    """
    owner = {character_id: user_id for user_id, character_id, *_rest in characters}
    names = {character_id: name for _user_id, character_id, name, *_rest in characters}
    # the hash of today is joined in, not read apart: the run reads the ownerships once
    earlier = (
        OwnershipRecord.objects.filter(character__character_id__in=list(owner))
        .exclude(owner_hash=F("character__character_ownership__owner_hash"))
        .values_list(
            "pk", "character__character_id", "created", "user__profile__main_character__character_name",
            "user__username",
        )
    )
    for record_id, character_id, created, main_name, username in earlier:
        suspect = accounts[owner[character_id]]
        who = main_name or username
        suspect.mark(OWNER_CHANGES, f"{names[character_id]}: {who}", character_id)
        rows = suspect.markers[OWNER_CHANGES].rows
        row = next((row for row in rows if row["character_id"] == character_id), None)
        if row is None:
            row = {"character": names[character_id], "character_id": character_id, "count": 0, "items": []}
            rows.append(row)
        row["count"] += 1
        # [record ID, day Auth first saw the owner, the owner's main or user name]
        row["items"].append([record_id, created.date().isoformat(), who])


def _add_membership(suspect, index, group_id, character_id, name, item_id, day):
    """One membership of a character in a hostile group, in the account's row of that group (user, 2026-11-27):
    the group is the finding, each membership an item a review covers - a new one reopens it."""
    rows = suspect.markers[MEMBERSHIP].rows
    row = next((row for row in rows if row["group_id"] == group_id), None)
    if row is None:
        row = {"group_id": group_id, "group": index.describe(group_id), "characters": [], "character_ids": []}
        row["items"] = []
        rows.append(row)
    if character_id not in row["character_ids"]:
        row["characters"].append(name)
        row["character_ids"].append(character_id)
    # [item ID, day joined ("" when Auth alone knows it), character, character ID]
    row["items"].append([item_id, day, name, character_id])


def _check_contacts(accounts, index, owner, names, audits, hostile_ids):
    from corptools.models import CharacterContact

    for audit_id, contact_id, standing in CharacterContact.objects.filter(
        standing__gt=0,
        character_id__in=list(audits),
        contact_id__in=hostile_ids,
    ).values_list("character_id", "contact_id", "standing"):
        character_id = audits[audit_id]
        suspect = accounts[owner[character_id]]
        # normalize: 5, not the column's 5.00
        standing = f"{standing.normalize():f}"
        suspect.mark(CONTACTS, f"{names[character_id]}: {index.describe(contact_id)} ({standing})", character_id)
        # the user's rule: one finding per main, contact and standing, the main's characters together
        rows = suspect.markers[CONTACTS].rows
        row = next((row for row in rows if (row["contact_id"], row["standing"]) == (contact_id, standing)), None)
        if row is None:
            row = {"contact_id": contact_id, "contact": index.describe(contact_id), "standing": standing}
            row.update(characters=[], character_ids=[])
            rows.append(row)
        row["characters"].append(names[character_id])
        row["character_ids"].append(character_id)


def _check_mails(accounts, index, owner, names, audits, hostile_ids, counterparts, since=None, tenure=None):
    from corptools.models import MailMessage

    mails = MailMessage.objects.filter(character_id__in=list(audits))
    recipients = MailMessage.recipients.through.objects.filter(
        mailmessage__character_id__in=list(audits), mailrecipient_id__in=hostile_ids
    )
    if since is not None:
        # corptools allows a mail without a timestamp: undated, it stays in rather than vanishing unseen
        mails = mails.filter(Q(timestamp__gte=since) | Q(timestamp__isnull=True))
        recipients = recipients.filter(
            Q(mailmessage__timestamp__gte=since) | Q(mailmessage__timestamp__isnull=True)
        )

    # the headers and the subject only: a mail body is never read (user)
    sent_by = [
        (*mail, RECEIVED)
        for mail in mails.filter(from_id__in=hostile_ids).values_list(
            "character_id", "mail_id", "from_id", "timestamp", "subject"
        )
    ]
    sent_to = [
        (*mail, SENT)
        for mail in recipients.values_list(
            "mailmessage__character_id",
            "mailmessage__mail_id",
            "mailrecipient_id",
            "mailmessage__timestamp",
            "mailmessage__subject",
        )
    ]
    if tenure is not None:
        tenure.prepare({mail[2] for mail in sent_by + sent_to})

    found = Found()  # (account, mail ID) -> hostile counterparts, own mailboxes
    dealings = defaultdict(Dealings)  # (account, own character, hostile) -> its mails
    for audit_id, mail_id, party_id, sent, subject, direction in sent_by + sent_to:
        character_id = audits[audit_id]
        if tenure is not None and not tenure.counts(character_id, sent):
            continue
        user_id = owner[character_id]
        parties = counterparts(user_id, sent, party_id)
        found.add((user_id, mail_id), parties, character_id)
        for party_id in parties:
            dealings[(user_id, character_id, party_id)].add(mail_id, sent, direction, subject=subject or "")
    # a mail in the boxes of two own characters counts once
    _mark_found(accounts, index, found, MAILS)
    _add_rows(accounts, index, names, dealings, MAILS)


def _check_wallet(
    accounts, index, owner, names, audits, hostile_ids, counterparts, since=None, ignored=(), tenure=None
):
    from corptools.models import CharacterWalletJournalEntry

    entries = CharacterWalletJournalEntry.objects.filter(
        Q(first_party_id__in=hostile_ids) | Q(second_party_id__in=hostile_ids),
        character_id__in=list(audits),
    ).exclude(ref_type__in=ignored)
    if since is not None:
        entries = entries.filter(date__gte=since)
    entries = without_public_contracts(entries)

    entries = list(
        entries.values_list(
            "pk", "character_id", "first_party_id", "second_party_id", "date", "ref_type", "amount", "entry_id"
        )
    )
    if tenure is not None:
        tenure.prepare({party_id for entry in entries for party_id in entry[2:4] if party_id in index})

    found = Found()
    dealings = defaultdict(Dealings)  # (account, own character, hostile) -> Dealings
    for pk, audit_id, first_party_id, second_party_id, date, ref_type, amount, entry_id in entries:
        character_id = audits[audit_id]
        if tenure is not None and not tenure.counts(character_id, date):
            continue
        user_id = owner[character_id]
        parties = counterparts(user_id, date, first_party_id, second_party_id)
        found.add((user_id, pk), parties, character_id)
        for party_id in parties:
            # EVE's ID, not corptools' row: a review keeps covering the entry should corptools fetch it anew
            dealings[(user_id, character_id, party_id)].add(entry_id, date, ref_type, amount)
    _mark_found(accounts, index, found, WALLET)
    _add_rows(accounts, index, names, dealings, WALLET)


def _check_contracts(accounts, index, owner, names, audits, hostile_ids, counterparts, since=None, tenure=None):
    from corptools.models import Contract

    contracts = Contract.objects.filter(character_id__in=list(audits)).exclude(availability=PUBLIC)
    if since is not None:
        contracts = contracts.filter(date_issued__gte=since)

    rows = list(contracts.filter(
        Q(issuer_id__in=hostile_ids)
        | Q(issuer_corporation_id__in=hostile_ids)
        | Q(assignee_id__in=hostile_ids)
        | Q(acceptor_id__in=hostile_ids),
    ).values_list(
        "character_id",
        "contract_id",
        "issuer_id",
        "issuer_corporation_id",
        "assignee_id",
        "acceptor_id",
        "date_issued",
        "contract_type",
        "price",
        "reward",
    ))
    if tenure is not None:
        tenure.prepare({party_id for row in rows for party_id in row[2:6] if party_id in index})

    found = Found()
    dealings = defaultdict(Dealings)
    for (
        audit_id,
        contract_id,
        issuer_id,
        issuer_corporation_id,
        assignee_id,
        acceptor_id,
        date_issued,
        contract_type,
        price,
        reward,
    ) in rows:
        character_id = audits[audit_id]
        if tenure is not None and not tenure.counts(character_id, date_issued):
            continue
        user_id = owner[character_id]
        parties = [issuer_id, assignee_id, acceptor_id]
        # the issuer's Corporation speaks for a stranger only: an own alt's Corporation is the membership marker
        if owner.get(issuer_id) != user_id:
            parties.append(issuer_corporation_id)
        parties = counterparts(user_id, date_issued, *parties)
        found.add((user_id, contract_id), parties, character_id)
        for party_id in parties:
            # what changes hands; the collateral is a deposit that comes back (user)
            dealings[(user_id, character_id, party_id)].add(
                contract_id, date_issued, contract_type, (price or 0) + (reward or 0)
            )
    _mark_found(accounts, index, found, CONTRACTS)
    _add_rows(accounts, index, names, dealings, CONTRACTS)


class Found:
    """Per (account, item) the hostile counterparts and the own characters whose records show them.

    One item (a mail, an entry, a contract) counts once however many own
    characters hold it; each of them stands behind the marker.
    """

    def __init__(self):
        self.parties = defaultdict(set)
        self.characters = defaultdict(set)

    def add(self, key: tuple, party_ids: set, character_id: int) -> None:
        # a record with no hostile left after dropping own characters puts nobody behind the marker
        if party_ids:
            self.parties[key] |= party_ids
            self.characters[key].add(character_id)


def _mark_found(accounts, index, found: Found, kind):
    for (user_id, item), party_ids in found.parties.items():
        marker = accounts[user_id].markers.setdefault(kind, Marker(kind))
        marker.count += 1
        marker.details.update(index.describe(party_id) for party_id in party_ids)
        marker.character_ids |= found.characters[(user_id, item)]


def _add_rows(accounts, index, names, dealings, kind):
    """One row per own character and hostile, the latest first."""
    # an undated mail has no last day: such a row goes last
    for (user_id, character_id, party_id), dealing in sorted(
        dealings.items(), key=lambda item: item[1].last.isoformat() if item[1].last else "", reverse=True
    ):
        # the plain name: Corporation and Alliance get columns of their own
        name = index.names.get(party_id) or str(party_id)
        accounts[user_id].markers[kind].rows.append(dealing.row(names[character_id], character_id, party_id, name))


AWOX = BlueKill.AWOX
BLUE = BlueKill.BLUE
# on a second copy only these may have changed: killtracker resolves the names after storing the killmail,
# and a copy made before the value was kept has none yet
RESOLVED_NAMES = ["victim", "victim_corporation", "victim_alliance", "ship", "value"]


def worth_counting(kills, config):
    """The blue kills at or above the minimum value and not of an ignored ship; one without a known value
    counts (user)."""
    if config.ignored_ships:
        kills = kills.exclude(ship__in=config.ignored_ships)
    if not config.min_kill_value:
        return kills
    return kills.filter(Q(value__isnull=True) | Q(value__gte=config.min_kill_value * 1_000_000))


def _check_kills(accounts, config, characters, tenure=None):
    """Killmails with an own character among the attackers and a victim in the Alliance or blue to it.

    What killtracker holds is copied into ``BlueKill`` first, the marker is
    read from there: killtracker deletes its killmails after a few days. One
    killmail counts once per account however many of its characters were on
    it; each of them gets a row.
    """
    owner = {character_id: user_id for user_id, character_id, *_rest in characters}
    names = {character_id: name for _user_id, character_id, name, *_rest in characters}
    alliance_id = config.alliance.alliance_id
    since = config.since()
    _copy_kills(alliance_id, owner, blue_entities(config), since, tenure)

    kills = worth_counting(BlueKill.objects.filter(alliance_id=alliance_id, character_id__in=list(owner)), config)
    if since is not None:
        kills = kills.filter(time__gte=since)
    seen = defaultdict(set)  # account -> killmail IDs
    for kill in kills.order_by("-time", "killmail_id", "character_id"):
        # a copy made before own kills were left out, or before the tenure counted
        if own_kill(owner, kill.character_id, kill.victim_id) or (
            tenure is not None and not tenure.counts(kill.character_id, kill.time)
        ):
            continue
        user_id = owner[kill.character_id]
        marker = accounts[user_id].markers.setdefault(BLUE_KILLS, Marker(BLUE_KILLS))
        if kill.killmail_id not in seen[user_id]:
            seen[user_id].add(kill.killmail_id)
            marker.count += 1
        # a structure has no character: its owner speaks for it
        marker.details.add(kill.victim or kill.victim_corporation)
        marker.character_ids.add(kill.character_id)
        marker.rows.append(
            {
                "character": names[kill.character_id],
                "character_id": kill.character_id,
                "killmail_id": kill.killmail_id,
                "date": kill.time.date().isoformat(),
                "victim": kill.victim,
                "victim_id": kill.victim_id,
                "corporation": kill.victim_corporation,
                "corporation_id": kill.victim_corporation_id,
                "alliance": kill.victim_alliance,
                "alliance_id": kill.victim_alliance_id,
                "ship": kill.ship,
                "million": million(kill.value),
                "reason": kill.reason,
                # normalize: 5, not the column's 5.0
                "standing": None if kill.standing is None else f"{kill.standing.normalize():f}",
            }
        )


def _check_capital_contracts(accounts, config, characters):
    """Open public contracts in which an own character offers a ship of a chosen capital group.

    The contracts come from ``capital_sweep``, which stores only open public ones; one that expired since
    is left out here. Only offered ships count (``is_included``), not those a want-to-buy asks for, and
    only a contract of a character of an account (a contract has one issuer, so it counts once).
    """
    owner = {character_id: user_id for user_id, character_id, *_rest in characters}
    names = {character_id: name for _user_id, character_id, name, *_rest in characters}
    items = CapitalContractItem.objects.filter(
        contract__issuer_id__in=list(owner),
        contract__date_expired__gt=timezone.now(),
        is_included=True,
        type__group__name__in=config.capital_ship_groups,
    ).values_list(
        "contract_id",
        "contract__issuer_id",
        "contract__contract_type",
        "contract__price",
        "contract__buyout",
        "contract__date_issued",
        "contract__date_expired",
        "contract__title",
        "contract__location",
        "type__name",
        "quantity",
    )
    contracts = {}  # (account, contract ID) -> the row, its ships still to be sorted
    for contract_id, issuer_id, kind, price, buyout, issued, expires, title, location, ship, quantity in items:
        user_id = owner[issuer_id]
        row = contracts.setdefault(
            (user_id, contract_id),
            {
                "character": names[issuer_id],
                "character_id": issuer_id,
                "contract_id": contract_id,
                "type": kind.replace("_", " "),
                "ships": {},
                "million": million(price),
                "buyout_million": million(buyout) if kind == "auction" else None,
                "issued": issued.date().isoformat(),
                "expires": expires.date().isoformat(),
                "title": title or "",
                "location": location or "",
            },
        )
        # two item rows of one ship type in a contract add up
        row["ships"][ship] = row["ships"].get(ship, 0) + quantity
    for (user_id, _contract_id), row in sorted(contracts.items(), key=lambda item: item[1]["expires"]):
        marker = accounts[user_id].markers.setdefault(CAPITAL_CONTRACTS, Marker(CAPITAL_CONTRACTS))
        ships = row["ships"]
        row["ships"] = [f"{quantity}x {ship}" if quantity > 1 else ship for ship, quantity in sorted(ships.items())]
        marker.count += 1
        marker.details.update(ships)
        marker.character_ids.add(row["character_id"])
        marker.rows.append(row)


def own_kill(owner: dict, attacker_id: int, victim_id: int | None) -> bool:
    """Attacker and victim are characters of one account: no awox, a player shot one of their own characters."""
    return victim_id in owner and owner[victim_id] == owner.get(attacker_id)


def _copy_kills(alliance_id, owner, blues, since, tenure=None):
    """Copy the blue kills killtracker holds into ``BlueKill``; one already copied keeps its reason.

    ``owner`` maps every character of the accounts to its user ID; a kill
    inside one account is not copied, nor one from before the character was in the Alliance.
    """

    def name(found: str, eve_id: int | None) -> str:
        # killtracker resolves the names after storing the killmail; the contact may know it already
        if found or not eve_id:
            return found
        return (blues[eve_id].name if eve_id in blues else "") or str(eve_id)

    copies = []
    for kill in killmails.kills(list(owner), alliance_id, list(blues), since):
        if own_kill(owner, kill.attacker_id, kill.victim_id) or (
            tenure is not None and not tenure.counts(kill.attacker_id, kill.time)
        ):
            continue
        # the victim first, then its Corporation, then its Alliance: the closest reason names the standing
        if kill.victim_alliance_id == alliance_id:
            reason, standing = AWOX, None
        else:
            blue = next(
                blues[entity_id]
                for entity_id in (kill.victim_id, kill.victim_corporation_id, kill.victim_alliance_id)
                if entity_id in blues
            )
            reason, standing = BLUE, blue.standing
        copies.append(
            BlueKill(
                alliance_id=alliance_id,
                killmail_id=kill.killmail_id,
                character_id=kill.attacker_id,
                time=kill.time,
                victim_id=kill.victim_id,
                victim=name(kill.victim_name, kill.victim_id),
                victim_corporation_id=kill.victim_corporation_id,
                victim_corporation=name(kill.victim_corporation, kill.victim_corporation_id),
                victim_alliance_id=kill.victim_alliance_id,
                victim_alliance=name(kill.victim_alliance, kill.victim_alliance_id),
                ship=kill.ship,
                value=kill.value,
                reason=reason,
                standing=standing,
            )
        )
    if copies:
        # MySQL takes the conflict from any unique key and refuses to be told which; sqlite needs it named
        unique = (
            ["alliance_id", "character_id", "killmail_id"]
            if connection.features.supports_update_conflicts_with_target
            else None
        )
        BlueKill.objects.bulk_create(copies, update_conflicts=True, unique_fields=unique, update_fields=RESOLVED_NAMES)
