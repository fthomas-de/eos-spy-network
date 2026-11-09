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
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from allianceauth.authentication.models import CharacterOwnership, UserProfile
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from . import killmails
from .hostiles import HostileIndex, blue_entities, hostile_index
from .models import BlueKill, SpyConfiguration

MEMBERSHIP = "membership"
CORP_CHANGES = "corp_changes"
CONTACTS = "contacts"
MAILS = "mails"
WALLET = "wallet"
CONTRACTS = "contracts"
BLUE_KILLS = "blue_kills"

# in this order on the pages
KINDS = (MEMBERSHIP, CORP_CHANGES, CONTACTS, MAILS, WALLET, CONTRACTS, BLUE_KILLS)

LABELS = {
    MEMBERSHIP: _("Hostile membership"),
    CORP_CHANGES: _("Frequent Corporation changes"),
    CONTACTS: _("Friendly to hostiles"),
    MAILS: _("Mails with hostiles"),
    WALLET: _("ISK with hostiles"),
    CONTRACTS: _("Contracts with hostiles"),
    BLUE_KILLS: _("Blue kills"),
}

DESCRIPTIONS = {
    MEMBERSHIP: _("A character is or was in a hostile Corporation or Alliance."),
    CORP_CHANGES: _("A character joined many Corporations within the last 365 days."),
    CONTACTS: _(
        "A character's own contacts hold a hostile with a positive standing."
    ),
    MAILS: _("Mails from or to hostiles."),
    WALLET: _("Wallet journal entries with hostiles."),
    CONTRACTS: _("Contracts with hostiles."),
    BLUE_KILLS: _("A character was on a killmail whose victim is in the Alliance (awox) or blue to it."),
}

# whose details are evidence: only shown with view_evidence
EVIDENCE = {MAILS, WALLET, CONTRACTS}

CORPTOOLS = "corptools"

# wallet entries that pay for a contract: corptools' journal names the contract in context_id
CONTRACT_REF_TYPES = (
    "contract_price",
    "contract_price_payment_corp",
    "contract_reward",
    "contract_collateral",
    "contract_collateral_payout",
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
    def affiliated(self) -> bool:
        """The rows name the counterpart's Corporation and Alliance; a snapshot of 0.0.5 (contacts: 0.0.16) or older does not."""
        return (self.dealings or self.contacts) and "alliance" in self.rows[0]

    @property
    def joins(self) -> bool:
        """Corporation changes name the Corporations in a tooltip per character."""
        return self.kind == CORP_CHANGES and bool(self.rows)

    @property
    def kills(self) -> bool:
        """Blue kills show their killmails as a table."""
        return self.kind == BLUE_KILLS and bool(self.rows)

    @property
    def contacts(self) -> bool:
        """Friendly hostile contacts show one row per contact and standing, with note and tick."""
        return self.kind == CONTACTS and bool(self.rows)


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

    def add(self, when: datetime, kind: str, isk=None) -> None:
        self.count += 1
        self.contract_payments = self.contract_payments or kind in CONTRACT_REF_TYPES
        self.isk += abs(isk or 0)
        self.first = when if self.first is None else min(self.first, when)
        self.last = when if self.last is None else max(self.last, when)
        self.types.add(kind.replace("_", " "))

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
            "first": self.first.date().isoformat(),
            "last": self.last.date().isoformat(),
            "types": sorted(self.types),
            "contract_payments": self.contract_payments,
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

    def counts(self) -> list[tuple]:
        """(marker label, description, number of suspects with it) for every marker found."""
        found = defaultdict(int)
        for suspect in self.suspects:
            for kind in suspect.markers:
                found[kind] += 1
        return [(LABELS[kind], DESCRIPTIONS[kind], found[kind]) for kind in KINDS if kind in found]


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
    mains = {
        profile.user_id: profile.main_character
        for profile in UserProfile.objects.filter(
            main_character__corporation_id__in=[corporation.corporation_id for corporation in corporations]
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
) -> list:
    """The Corporations of the configured Alliance, each with its marked accounts; with
    ``corporation_id`` only that one. ``step`` is told the name of each check as it starts.
    ``hostiles`` (``hostile_entities``) and ``members`` (``roster``) save reading them twice."""
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
        tiles[main.corporation_id].mains += 1

    step("hostiles")
    index = hostile_index(config, hostiles)
    if accounts and index:
        _check(accounts, index, config, members.characters, step)
    # blue kills need no hostile: the victim is a friend
    if accounts:
        step("kills")
        _check_kills(accounts, config, members.characters)

    for suspect in accounts.values():
        if suspect.markers:
            tiles[suspect.main.corporation_id].suspects.append(suspect)
    for tile in tiles.values():
        tile.suspects.sort(key=by_markers)
    return list(tiles.values())


def _check(accounts: dict, index: HostileIndex, config: SpyConfiguration, characters: list, step=_no_step) -> None:
    step("membership")
    # EVE ID of every character -> its account; a character of the own account is never a counterpart
    owner = {}
    names = {}
    for user_id, character_id, name, corporation_id, alliance_id in characters:
        owner[character_id] = user_id
        names[character_id] = name
        accounts[user_id].character_count += 1
        for group_id in (corporation_id, alliance_id):
            if group_id in index:
                accounts[user_id].mark(MEMBERSHIP, f"{name}: {index.describe(group_id)}", character_id)
                break

    if not corptools_installed():
        return

    own = defaultdict(set)
    for character_id, user_id in owner.items():
        own[user_id].add(character_id)

    def counterparts(user_id, *party_ids):
        return {party_id for party_id in party_ids if party_id in index and party_id not in own[user_id]}

    audits = character_audits(list(owner))
    hostile_ids = index.ids
    # the hostile list is today's: the further back, the likelier a hostile was a friend then
    since = config.since()
    step("history")
    _check_history(accounts, index, config, owner, names, audits, since)
    step("contacts")
    # contacts carry no date in corptools: today's are checked whatever the time frame
    _check_contacts(accounts, index, owner, names, audits, hostile_ids)
    step("mails")
    _check_mails(accounts, index, owner, audits, hostile_ids, counterparts, since)
    step("wallet")
    _check_wallet(
        accounts, index, owner, names, audits, hostile_ids, counterparts, since, config.ignored_ref_types or ()
    )
    step("contracts")
    _check_contracts(accounts, index, owner, names, audits, hostile_ids, counterparts, since)


def _check_history(accounts, index, config, owner, names, audits, since=None):
    from corptools.models import CorporationHistory

    year_ago = timezone.now() - timedelta(days=365)
    records = defaultdict(list)  # character -> [(start date, Corporation ID, Corporation name)]
    for audit_id, corporation_id, corporation_name, start_date in CorporationHistory.objects.filter(
        character_id__in=list(audits)
    ).values_list("character_id", "corporation_id", "corporation_name__name", "start_date"):
        records[audits[audit_id]].append((start_date, corporation_id, corporation_name or str(corporation_id)))

    joined = defaultdict(list)  # character -> [(start date, Corporation name)]
    for character_id, history in records.items():
        history.sort()
        # a membership ends where the next one starts; the last one lasts until today
        ends = [following[0] for following in history[1:]] + [None]
        for (start_date, corporation_id, corporation_name), end_date in zip(history, ends):
            if corporation_id in index and (since is None or end_date is None or end_date >= since):
                accounts[owner[character_id]].mark(
                    MEMBERSHIP, f"{names[character_id]}: {index.describe(corporation_id)}", character_id
                )
            if start_date >= year_ago:
                joined[character_id].append((start_date, corporation_name))
    for character_id, corporations in joined.items():
        count = len(corporations)
        if count >= config.corp_changes_per_year:
            suspect = accounts[owner[character_id]]
            suspect.mark(CORP_CHANGES, f"{names[character_id]}: {count}", character_id, count)
            suspect.markers[CORP_CHANGES].rows.append(
                {
                    "character": names[character_id],
                    "count": count,
                    "corporations": [[start.date().isoformat(), name] for start, name in sorted(corporations)],
                }
            )


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


def _check_mails(accounts, index, owner, audits, hostile_ids, counterparts, since=None):
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

    found = Found()  # (account, mail ID) -> hostile counterparts, own mailboxes
    for audit_id, mail_id, from_id in mails.filter(from_id__in=hostile_ids).values_list(
        "character_id", "mail_id", "from_id"
    ):
        character_id = audits[audit_id]
        user_id = owner[character_id]
        found.add((user_id, mail_id), counterparts(user_id, from_id), character_id)
    for audit_id, mail_id, recipient_id in recipients.values_list(
        "mailmessage__character_id", "mailmessage__mail_id", "mailrecipient_id"
    ):
        character_id = audits[audit_id]
        user_id = owner[character_id]
        found.add((user_id, mail_id), counterparts(user_id, recipient_id), character_id)
    # a mail in the boxes of two own characters counts once
    _mark_found(accounts, index, found, MAILS)


def _check_wallet(accounts, index, owner, names, audits, hostile_ids, counterparts, since=None, ignored=()):
    from corptools.models import CharacterWalletJournalEntry

    entries = CharacterWalletJournalEntry.objects.filter(
        Q(first_party_id__in=hostile_ids) | Q(second_party_id__in=hostile_ids),
        character_id__in=list(audits),
    ).exclude(ref_type__in=ignored)
    if since is not None:
        entries = entries.filter(date__gte=since)

    found = Found()
    dealings = defaultdict(Dealings)  # (account, own character, hostile) -> Dealings
    for pk, audit_id, first_party_id, second_party_id, date, ref_type, amount in entries.values_list(
        "pk", "character_id", "first_party_id", "second_party_id", "date", "ref_type", "amount"
    ):
        character_id = audits[audit_id]
        user_id = owner[character_id]
        parties = counterparts(user_id, first_party_id, second_party_id)
        found.add((user_id, pk), parties, character_id)
        for party_id in parties:
            dealings[(user_id, character_id, party_id)].add(date, ref_type, amount)
    _mark_found(accounts, index, found, WALLET)
    _add_rows(accounts, index, names, dealings, WALLET)


def _check_contracts(accounts, index, owner, names, audits, hostile_ids, counterparts, since=None):
    from corptools.models import Contract

    contracts = Contract.objects.filter(character_id__in=list(audits))
    if since is not None:
        contracts = contracts.filter(date_issued__gte=since)

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
    ) in contracts.filter(
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
    ):
        character_id = audits[audit_id]
        user_id = owner[character_id]
        parties = [issuer_id, assignee_id, acceptor_id]
        # the issuer's Corporation speaks for a stranger only: an own alt's Corporation is the membership marker
        if owner.get(issuer_id) != user_id:
            parties.append(issuer_corporation_id)
        parties = counterparts(user_id, *parties)
        found.add((user_id, contract_id), parties, character_id)
        for party_id in parties:
            # what changes hands; the collateral is a deposit that comes back (user)
            dealings[(user_id, character_id, party_id)].add(date_issued, contract_type, (price or 0) + (reward or 0))
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
    for (user_id, character_id, party_id), dealing in sorted(
        dealings.items(), key=lambda item: item[1].last, reverse=True
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
    """The blue kills at or above the minimum value; one without a known value counts (user)."""
    if not config.min_kill_value:
        return kills
    return kills.filter(Q(value__isnull=True) | Q(value__gte=config.min_kill_value * 1_000_000))


def _check_kills(accounts, config, characters):
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
    _copy_kills(alliance_id, owner, blue_entities(config), since)

    kills = worth_counting(BlueKill.objects.filter(alliance_id=alliance_id, character_id__in=list(owner)), config)
    if since is not None:
        kills = kills.filter(time__gte=since)
    seen = defaultdict(set)  # account -> killmail IDs
    for kill in kills.order_by("-time", "killmail_id", "character_id"):
        # a copy made before own kills were left out
        if own_kill(owner, kill.character_id, kill.victim_id):
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


def own_kill(owner: dict, attacker_id: int, victim_id: int | None) -> bool:
    """Attacker and victim are characters of one account: no awox, a player shot one of their own characters."""
    return victim_id in owner and owner[victim_id] == owner.get(attacker_id)


def _copy_kills(alliance_id, owner, blues, since):
    """Copy the blue kills killtracker holds into ``BlueKill``; one already copied keeps its reason.

    ``owner`` maps every character of the accounts to its user ID; a kill
    inside one account is not copied.
    """

    def name(found: str, eve_id: int | None) -> str:
        # killtracker resolves the names after storing the killmail; the contact may know it already
        if found or not eve_id:
            return found
        return (blues[eve_id].name if eve_id in blues else "") or str(eve_id)

    copies = []
    for kill in killmails.kills(list(owner), alliance_id, list(blues), since):
        if own_kill(owner, kill.attacker_id, kill.victim_id):
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
