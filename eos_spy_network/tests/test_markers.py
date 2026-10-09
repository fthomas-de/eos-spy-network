from datetime import timedelta
from unittest.mock import patch

from corptools.models import (
    CharacterAudit,
    CharacterContact,
    CharacterWalletJournalEntry,
    Contract,
    CorporationHistory,
    EveName,
    MailMessage,
    MailRecipient,
)

from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCorporationInfo

from eos_spy_network import markers
from eos_spy_network.hostiles import hostile_index
from eos_spy_network.models import ContactSource

from .base import ALLIANCE_ID, SpyTestCase, add_contact, add_token, configure, make_alliance, make_character, make_corporation, make_user

HOSTILE_CORP = 98000001
HOSTILE_ALLIANCE = 99000001
CORP_OF_HOSTILE_ALLIANCE = 98000002
NEUTRAL_CORP = 98000003
HOSTILE_MEMBER = 90000001  # a character Auth knows, in the hostile Corporation
NOT_INSTALLED = "eos_spy_network.markers.corptools_installed"


def eve_name(eve_id, category="character"):
    return EveName.objects.get_or_create(eve_id=eve_id, defaults={"name": f"Name {eve_id}", "category": category})[0]


class MarkerTestCase(SpyTestCase):
    def setUp(self):
        super().setUp()
        configure()
        make_corporation(2001)
        EveCorporationInfo.objects.create(
            corporation_id=HOSTILE_CORP, corporation_name="Bad Corp", corporation_ticker="BAD", member_count=1
        )
        make_alliance(HOSTILE_ALLIANCE)
        make_corporation(CORP_OF_HOSTILE_ALLIANCE, alliance_id=HOSTILE_ALLIANCE)
        ContactSource.objects.create(kind=ContactSource.ALLIANCE, entity_id=ALLIANCE_ID, name="Us")
        add_token(ContactSource.ALLIANCE, ALLIANCE_ID)
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, HOSTILE_CORP, -10)
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, HOSTILE_ALLIANCE, -5, contact_type="alliance")
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, NEUTRAL_CORP, 0)
        make_character(HOSTILE_MEMBER, corporation_id=HOSTILE_CORP, alliance_id=None)

        self.user = make_user("suspect")
        self.main = self.user.profile.main_character
        self.audit = CharacterAudit.objects.create(character=self.main)

    def add_alt(self, character_id, corporation_id=2001, alliance_id=ALLIANCE_ID):
        alt = make_character(character_id, corporation_id=corporation_id, alliance_id=alliance_id)
        CharacterOwnership.objects.create(user=self.user, character=alt, owner_hash=f"hash-{character_id}")
        return alt

    def suspect(self):
        """The test account's entry on its Corporation's tile, None without markers."""
        (tile,) = markers.corporation_tiles(corporation_id=2001)
        return next((suspect for suspect in tile.suspects if suspect.user_id == self.user.pk), None)

    def kinds(self):
        suspect = self.suspect()
        return set(suspect.markers) if suspect else set()


class TestHostileIndex(MarkerTestCase):
    def test_should_take_in_known_members_of_hostile_groups(self):
        index = hostile_index()

        self.assertIn(HOSTILE_CORP, index)
        self.assertIn(CORP_OF_HOSTILE_ALLIANCE, index)
        self.assertIn(HOSTILE_MEMBER, index)
        self.assertNotIn(NEUTRAL_CORP, index)
        self.assertEqual(index.describe(HOSTILE_MEMBER), f"Char {HOSTILE_MEMBER} (Bad Corp)")

    def test_should_take_in_known_members_of_a_hostile_alliance(self):
        # its Corporation is no contact itself: the Alliance makes the character hostile
        make_character(90000002, corporation_id=CORP_OF_HOSTILE_ALLIANCE, alliance_id=HOSTILE_ALLIANCE)

        self.assertIn(90000002, hostile_index())


class TestCorporationTiles(MarkerTestCase):
    def test_should_list_the_corporations_of_the_alliance_only(self):
        make_corporation(2002)

        tiles = markers.corporation_tiles()

        self.assertEqual([tile.id for tile in tiles], [2001, 2002])
        self.assertEqual(tiles[0].mains, 1)
        self.assertEqual(tiles[0].suspects, [])

    def test_should_offer_nothing_without_an_alliance(self):
        configure(alliance_id=None)

        self.assertEqual(markers.corporation_tiles(), [])

    def test_should_count_the_mains_with_each_marker(self):
        self.add_alt(5001, corporation_id=HOSTILE_CORP, alliance_id=None)

        (tile,) = markers.corporation_tiles(corporation_id=2001)

        self.assertEqual(tile.counts(), [(markers.LABELS[markers.MEMBERSHIP], markers.DESCRIPTIONS[markers.MEMBERSHIP], 1)])


class TestMembership(MarkerTestCase):
    def test_should_mark_an_alt_in_a_hostile_corporation(self):
        self.add_alt(5001, corporation_id=HOSTILE_CORP, alliance_id=None)

        marker = self.suspect().markers[markers.MEMBERSHIP]

        self.assertEqual(marker.details, {"Char 5001: Bad Corp"})

    def test_should_mark_an_alt_in_a_hostile_alliance(self):
        self.add_alt(5001, corporation_id=CORP_OF_HOSTILE_ALLIANCE, alliance_id=HOSTILE_ALLIANCE)

        self.assertEqual(self.kinds(), {markers.MEMBERSHIP})

    def test_should_mark_a_hostile_corporation_in_the_history(self):
        CorporationHistory.objects.create(
            character=self.audit,
            corporation_id=HOSTILE_CORP,
            corporation_name=eve_name(HOSTILE_CORP, "corporation"),
            record_id=1,
            start_date=timezone.now() - timedelta(days=900),
        )

        self.assertEqual(self.kinds(), {markers.MEMBERSHIP})

    def test_should_leave_a_clean_account_out(self):
        self.add_alt(5001, corporation_id=NEUTRAL_CORP, alliance_id=None)

        self.assertIsNone(self.suspect())

    def test_should_check_the_current_corporation_without_corptools(self):
        self.add_alt(5001, corporation_id=HOSTILE_CORP, alliance_id=None)
        CharacterContact.objects.create(
            id=1, character=self.audit, contact_id=HOSTILE_CORP, contact_type="corporation",
            contact_name=eve_name(HOSTILE_CORP, "corporation"), standing=5,
        )

        with patch(NOT_INSTALLED, return_value=False):
            self.assertEqual(self.kinds(), {markers.MEMBERSHIP})


class TestCorporationChanges(MarkerTestCase):
    def add_history(self, *days_ago):
        for record_id, days in enumerate(days_ago, 1):
            CorporationHistory.objects.create(
                character=self.audit,
                corporation_id=1000000 + record_id,
                corporation_name=eve_name(1000000 + record_id, "corporation"),
                record_id=record_id,
                start_date=timezone.now() - timedelta(days=days),
            )

    def test_should_mark_as_many_joins_as_configured_within_a_year(self):
        configure(corp_changes_per_year=3)
        self.add_history(10, 100, 300)

        marker = self.suspect().markers[markers.CORP_CHANGES]

        self.assertEqual(marker.count, 3)

    def test_should_name_the_corporations_joined_oldest_first(self):
        configure(corp_changes_per_year=2)
        self.add_history(100, 10)

        (row,) = self.suspect().markers[markers.CORP_CHANGES].rows

        self.assertEqual((row["character"], row["count"]), (self.main.character_name, 2))
        self.assertEqual([name for _start, name in row["corporations"]], ["Name 1000001", "Name 1000002"])
        self.assertEqual(
            row["corporations"][0][0], (timezone.now() - timedelta(days=100)).date().isoformat()
        )

    def test_should_not_count_joins_older_than_a_year(self):
        configure(corp_changes_per_year=3)
        self.add_history(10, 100, 400)

        self.assertIsNone(self.suspect())


class TestContacts(MarkerTestCase):
    def add_contact(self, contact_id, standing, watched=False):
        CharacterContact.objects.create(
            id=contact_id, character=self.audit, contact_id=contact_id, contact_type="corporation",
            contact_name=eve_name(contact_id, "corporation"), standing=standing, watched=watched,
        )

    def test_should_mark_a_positive_standing_to_a_hostile(self):
        self.add_contact(HOSTILE_CORP, 5)

        marker = self.suspect().markers[markers.CONTACTS]

        self.assertEqual(marker.details, {f"{self.main.character_name}: Bad Corp (5)"})

    def test_should_mark_a_watched_hostile(self):
        self.add_contact(HOSTILE_CORP, -10, watched=True)

        self.assertEqual(self.kinds(), {markers.CONTACTS})

    def test_should_ignore_a_hostile_kept_as_enemy(self):
        self.add_contact(HOSTILE_CORP, -10)

        self.assertIsNone(self.suspect())

    def test_should_ignore_friends_that_are_not_hostile(self):
        self.add_contact(NEUTRAL_CORP, 10)

        self.assertIsNone(self.suspect())


class TestMails(MarkerTestCase):
    def add_mail(self, id_key, mail_id, from_id, audit=None, recipients=()):
        mail = MailMessage.objects.create(id_key=id_key, character=audit or self.audit, mail_id=mail_id, from_id=from_id)
        for recipient_id in recipients:
            recipient, _ = MailRecipient.objects.get_or_create(recipient_id=recipient_id, recipient_type="character")
            mail.recipients.add(recipient)
        return mail

    def test_should_mark_a_mail_from_a_hostile(self):
        self.add_mail(1, 1, HOSTILE_MEMBER)

        marker = self.suspect().markers[markers.MAILS]

        self.assertEqual((marker.count, marker.details), (1, {f"Char {HOSTILE_MEMBER} (Bad Corp)"}))

    def test_should_mark_a_mail_to_a_hostile(self):
        self.add_mail(1, 1, self.main.character_id, recipients=[HOSTILE_CORP])

        self.assertEqual(self.kinds(), {markers.MAILS})

    def test_should_count_a_mail_in_two_own_boxes_once(self):
        alt_audit = CharacterAudit.objects.create(character=self.add_alt(5001))
        self.add_mail(1, 7, HOSTILE_MEMBER)
        self.add_mail(2, 7, HOSTILE_MEMBER, audit=alt_audit)

        self.assertEqual(self.suspect().markers[markers.MAILS].count, 1)

    def test_should_ignore_mails_between_own_characters(self):
        # the alt is in a hostile Corporation: that is the membership marker, not a mail with a hostile
        alt = self.add_alt(5001, corporation_id=HOSTILE_CORP, alliance_id=None)
        self.add_mail(1, 1, alt.character_id)

        self.assertEqual(self.kinds(), {markers.MEMBERSHIP})


class TestWallet(MarkerTestCase):
    def add_entry(self, entry_id, first_party_id, second_party_id, amount=1, days_ago=0, ref_type="player_donation"):
        CharacterWalletJournalEntry.objects.create(
            character=self.audit, entry_id=entry_id, date=timezone.now() - timedelta(days=days_ago), description="",
            ref_type=ref_type, first_party_id=first_party_id, second_party_id=second_party_id, amount=amount,
            balance=1,
        )

    def test_should_sum_up_the_entries_per_hostile(self):
        self.add_entry(1, HOSTILE_CORP, self.main.character_id, amount=500, days_ago=30)
        self.add_entry(2, self.main.character_id, HOSTILE_CORP, amount=-200, ref_type="player_trading")

        (row,) = self.suspect().markers[markers.WALLET].rows

        self.assertEqual(
            {key: row[key] for key in ("character", "counterpart", "count", "isk", "types")},
            {
                "character": self.main.character_name,
                "counterpart": "Bad Corp",
                "count": 2,
                "isk": "700.00",
                "types": ["player donation", "player trading"],
            },
        )
        self.assertEqual(row["first"], (timezone.now() - timedelta(days=30)).date().isoformat())
        self.assertEqual(row["last"], timezone.now().date().isoformat())

    def test_should_mark_isk_from_a_known_member_of_a_hostile_corporation(self):
        self.add_entry(1, HOSTILE_MEMBER, self.main.character_id)
        self.add_entry(2, self.main.character_id, HOSTILE_CORP)

        marker = self.suspect().markers[markers.WALLET]

        self.assertEqual(marker.count, 2)
        self.assertEqual(marker.details, {"Bad Corp", f"Char {HOSTILE_MEMBER} (Bad Corp)"})

    def test_should_ignore_isk_with_an_own_alt(self):
        alt = self.add_alt(5001, corporation_id=HOSTILE_CORP, alliance_id=None)
        self.add_entry(1, alt.character_id, self.main.character_id)

        self.assertEqual(self.kinds(), {markers.MEMBERSHIP})


class TestContracts(MarkerTestCase):
    def add_contract(self, contract_id, issuer_id, issuer_corporation_id, assignee_id, acceptor_id=0, days_ago=0):
        now = timezone.now() - timedelta(days=days_ago)
        Contract.objects.create(
            id=f"{self.audit.pk}-{contract_id}", contract_id=contract_id, character=self.audit,
            issuer_id=issuer_id, issuer_name=eve_name(issuer_id),
            issuer_corporation_id=issuer_corporation_id, issuer_corporation_name=eve_name(issuer_corporation_id, "corporation"),
            assignee_id=assignee_id, assignee_name=eve_name(assignee_id),
            acceptor_id=acceptor_id, acceptor_name=eve_name(acceptor_id),
            for_corporation=False, date_expired=now, date_issued=now, status="finished",
            contract_type="item_exchange", availability="personal", title="",
        )

    def test_should_mark_a_contract_to_a_hostile(self):
        self.add_contract(1, self.main.character_id, 2001, HOSTILE_MEMBER)

        self.assertEqual(self.kinds(), {markers.CONTRACTS})

    def test_should_give_the_period_of_the_contracts_per_hostile(self):
        self.add_contract(1, self.main.character_id, 2001, HOSTILE_CORP, days_ago=60)
        self.add_contract(2, self.main.character_id, 2001, HOSTILE_CORP)

        (row,) = self.suspect().markers[markers.CONTRACTS].rows

        self.assertEqual((row["count"], row["types"]), (2, ["item exchange"]))
        self.assertEqual(
            (row["first"], row["last"]),
            ((timezone.now() - timedelta(days=60)).date().isoformat(), timezone.now().date().isoformat()),
        )

    def test_should_mark_a_contract_by_a_stranger_of_a_hostile_corporation(self):
        self.add_contract(1, 5555, HOSTILE_CORP, self.main.character_id)

        self.assertEqual(self.suspect().markers[markers.CONTRACTS].details, {"Bad Corp"})

    def test_should_ignore_the_corporation_of_an_own_issuing_alt(self):
        alt = self.add_alt(5001, corporation_id=HOSTILE_CORP, alliance_id=None)
        self.add_contract(1, alt.character_id, HOSTILE_CORP, self.main.character_id)

        self.assertEqual(self.kinds(), {markers.MEMBERSHIP})
