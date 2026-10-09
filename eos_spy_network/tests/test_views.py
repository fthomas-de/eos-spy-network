from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from eos_spy_network.models import ContactSource, SpyConfiguration

from .base import (
    ALLIANCE_ID,
    SpyTestCase,
    add_contact,
    add_token,
    configure,
    make_alliance,
    make_character,
    make_corporation,
    make_user,
)

VIEW_SUSPECTS = "eos_spy_network.view_suspects"
VIEW_EVIDENCE = "eos_spy_network.view_evidence"
MANAGE_SETTINGS = "eos_spy_network.manage_settings"
# user_passes_test sends a user without the permission to the login page
LOGIN = "/account/login/"
NOT_INSTALLED = "eos_spy_network.contacts.is_installed"
HOSTILE_CORP = 98000001


class TestAccess(SpyTestCase):
    def test_should_turn_away_users_without_permission(self):
        self.client.force_login(make_user("nobody"))

        for url in (
            reverse("eos_spy_network:index"),
            reverse("eos_spy_network:corporations"),
            reverse("eos_spy_network:corporation", args=[2001]),
            reverse("eos_spy_network:settings"),
        ):
            with self.subTest(url):
                response = self.client.get(url)
                self.assertTrue(response.url.startswith(LOGIN))

    def test_should_keep_settings_from_viewers(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:settings"))

        self.assertTrue(response.url.startswith(LOGIN))

    def test_should_keep_the_corporations_from_settings_managers(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS))

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertTrue(response.url.startswith(LOGIN))

    def test_should_send_viewers_to_the_corporations(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:index"))

        self.assertRedirects(response, reverse("eos_spy_network:corporations"))

    def test_should_send_settings_managers_to_the_settings(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS))

        response = self.client.get(reverse("eos_spy_network:index"))

        self.assertRedirects(response, reverse("eos_spy_network:settings"))

    def test_should_send_holders_of_both_to_the_corporations(self):
        self.client.force_login(make_user("lead", VIEW_SUSPECTS, MANAGE_SETTINGS))

        response = self.client.get(reverse("eos_spy_network:index"))

        self.assertRedirects(response, reverse("eos_spy_network:corporations"))


class SuspectPageTestCase(SpyTestCase):
    """An Alliance with a hostile Corporation, and a member with an alt in it."""

    def setUp(self):
        super().setUp()
        configure()
        make_corporation(2001)
        # the names come from Auth's own table, as aa-contacts' annotation reads them
        EveCorporationInfo.objects.create(
            corporation_id=HOSTILE_CORP, corporation_name="Bad Corp", corporation_ticker="BAD", member_count=1
        )
        ContactSource.objects.create(kind=ContactSource.ALLIANCE, entity_id=ALLIANCE_ID, name="Us")
        add_token(ContactSource.ALLIANCE, ALLIANCE_ID)
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, HOSTILE_CORP, -10)

        suspect = make_user("suspect")
        alt = make_character(5001, corporation_id=HOSTILE_CORP, alliance_id=None)
        CharacterOwnership.objects.create(user=suspect, character=alt, owner_hash="hash-5001")
        self.suspect_main = suspect.profile.main_character


class TestCorporationsPage(SuspectPageTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

    def test_should_show_a_tile_per_corporation(self):
        make_corporation(2002)

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, reverse("eos_spy_network:corporation", args=[2001]))
        self.assertContains(response, reverse("eos_spy_network:corporation", args=[2002]))
        self.assertContains(response, "Hostile membership")
        self.assertNotContains(response, "No contacts in aa-contacts yet")

    def test_should_say_that_no_alliance_is_configured(self):
        configure(alliance_id=None)

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "No Alliance is configured yet.")

    def test_should_say_that_no_source_is_ticked(self):
        ContactSource.objects.all().delete()

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "No contact source is ticked")

    def test_should_name_sources_without_contacts(self):
        ContactSource.objects.create(kind=ContactSource.CORPORATION, entity_id=2001, name="Tokenless Corp")
        ContactSource.objects.create(kind=ContactSource.CORPORATION, entity_id=2002, name="Unread Corp")
        ContactSource.objects.create(kind=ContactSource.CORPORATION, entity_id=2003, name="Read Corp")
        add_token(ContactSource.CORPORATION, 2002, contacts_modified=False)
        add_token(ContactSource.CORPORATION, 2003)

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "Tokenless Corp")
        self.assertContains(response, "Unread Corp")
        # case-sensitive: "Unread Corp" does not contain it
        self.assertNotContains(response, "Read Corp")

    def test_should_say_that_aa_contacts_is_missing(self):
        with patch(NOT_INSTALLED, return_value=False):
            response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "aa-contacts is not installed")

    def test_should_say_that_corptools_is_missing(self):
        with patch("eos_spy_network.views.corptools_installed", return_value=False):
            response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "corptools is not installed")


class TestCorporationPage(SuspectPageTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

    def test_should_list_the_marked_mains(self):
        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, self.suspect_main.character_name)
        self.assertContains(response, "Char 5001: Bad Corp")
        # the viewer has no marker and is no suspect; its name is in the navbar, so not by text
        self.assertEqual([suspect.main for suspect in response.context["tile"].suspects], [self.suspect_main])

    def test_should_refuse_a_corporation_outside_the_alliance(self):
        make_corporation(2999, alliance_id=None)

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2999]))

        self.assertEqual(response.status_code, 404)


class TestEvidence(SuspectPageTestCase):
    # the wallet entry's counterpart alone; the membership marker names "Char 5001: Bad Corp"
    COUNTERPART = ">Bad Corp</span>"

    def setUp(self):
        super().setUp()
        from corptools.models import CharacterAudit, CharacterWalletJournalEntry

        main = EveCharacter.objects.get(pk=self.suspect_main.pk)
        CharacterWalletJournalEntry.objects.create(
            character=CharacterAudit.objects.create(character=main),
            entry_id=1,
            date=timezone.now(),
            description="",
            ref_type="player_donation",
            first_party_id=HOSTILE_CORP,
            second_party_id=main.character_id,
            amount=1,
            balance=1,
        )

    def test_should_hide_the_counterparts_without_view_evidence(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, "ISK with hostiles")
        self.assertNotContains(response, self.COUNTERPART)

    def test_should_show_the_counterparts_with_view_evidence(self):
        self.client.force_login(make_user("lead", VIEW_SUSPECTS, VIEW_EVIDENCE))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, self.COUNTERPART)


class TestSettingsPage(SpyTestCase):
    def setUp(self):
        super().setUp()
        make_corporation(2001)
        make_corporation(2002)
        self.client.force_login(make_user("admin", MANAGE_SETTINGS))

    def test_should_list_the_alliance_and_its_corporations(self):
        configure()

        response = self.client.get(reverse("eos_spy_network:settings"))

        self.assertContains(response, f'value="alliance:{ALLIANCE_ID}"')
        self.assertContains(response, 'value="corporation:2001"')
        self.assertContains(response, 'value="corporation:2002"')
        self.assertContains(response, reverse("aa_contacts:index"))

    def test_should_save_the_ticked_sources(self):
        configure()

        response = self.client.post(
            reverse("eos_spy_network:settings"),
            {
                "alliance": make_alliance().pk,
                "hostile_below": "-5",
                "corp_changes_per_year": "6",
                "source": ["corporation:2002"],
            },
        )

        self.assertRedirects(response, reverse("eos_spy_network:settings"))
        self.assertEqual(list(ContactSource.objects.values_list("entity_id", flat=True)), [2002])
        config = SpyConfiguration.get_solo()
        self.assertEqual(config.hostile_below, Decimal("-5"))
        self.assertEqual(config.corp_changes_per_year, 6)

    def test_should_reject_a_threshold_out_of_range(self):
        configure()

        response = self.client.post(
            reverse("eos_spy_network:settings"),
            {"alliance": make_alliance().pk, "hostile_below": "-11", "corp_changes_per_year": "4"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SpyConfiguration.get_solo().hostile_below, Decimal("0"))

    def test_should_render_without_aa_contacts(self):
        configure()

        with patch(NOT_INSTALLED, return_value=False):
            response = self.client.get(reverse("eos_spy_network:settings"))

        self.assertContains(response, "aa-contacts is not installed")
        self.assertNotContains(response, "Open aa-contacts")
