from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse

from allianceauth.eveonline.models import EveCorporationInfo

from eos_spy_network.models import ContactSource, SpyConfiguration

from .base import ALLIANCE_ID, SpyTestCase, add_contact, add_token, configure, make_alliance, make_corporation, make_user

VIEW_SUSPECTS = "eos_spy_network.view_suspects"
VIEW_EVIDENCE = "eos_spy_network.view_evidence"
MANAGE_SETTINGS = "eos_spy_network.manage_settings"
# user_passes_test sends a user without the permission to the login page
LOGIN = "/account/login/"
NOT_INSTALLED = "eos_spy_network.contacts.is_installed"


class TestAccess(SpyTestCase):
    def test_should_turn_away_users_without_permission(self):
        self.client.force_login(make_user("nobody"))

        for name in ("index", "hostiles", "settings"):
            with self.subTest(name):
                response = self.client.get(reverse(f"eos_spy_network:{name}"))
                self.assertTrue(response.url.startswith(LOGIN))

    def test_should_keep_settings_from_viewers(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:settings"))

        self.assertTrue(response.url.startswith(LOGIN))

    def test_should_keep_the_hostile_list_from_settings_managers(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS))

        response = self.client.get(reverse("eos_spy_network:hostiles"))

        self.assertTrue(response.url.startswith(LOGIN))

    def test_should_send_viewers_to_the_hostile_list(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:index"))

        self.assertRedirects(response, reverse("eos_spy_network:hostiles"))

    def test_should_send_settings_managers_to_the_settings(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS))

        response = self.client.get(reverse("eos_spy_network:index"))

        self.assertRedirects(response, reverse("eos_spy_network:settings"))

    def test_should_send_holders_of_both_to_the_hostile_list(self):
        self.client.force_login(make_user("lead", VIEW_SUSPECTS, MANAGE_SETTINGS))

        response = self.client.get(reverse("eos_spy_network:index"))

        self.assertRedirects(response, reverse("eos_spy_network:hostiles"))


class TestHostilesPage(SpyTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

    def test_should_show_hostile_contacts(self):
        configure()
        # the names come from Auth's own table, as aa-contacts' annotation reads them
        EveCorporationInfo.objects.create(
            corporation_id=98000001, corporation_name="Bad Corp", corporation_ticker="BAD", member_count=1
        )
        EveCorporationInfo.objects.create(
            corporation_id=98000002, corporation_name="Nice Corp", corporation_ticker="NICE", member_count=1
        )
        ContactSource.objects.create(kind=ContactSource.ALLIANCE, entity_id=ALLIANCE_ID, name="Us")
        add_token(ContactSource.ALLIANCE, ALLIANCE_ID)
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, 98000001, -10)
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, 98000002, 5)

        response = self.client.get(reverse("eos_spy_network:hostiles"))

        self.assertContains(response, "Bad Corp")
        self.assertNotContains(response, "Nice Corp")
        self.assertNotContains(response, "No contacts in aa-contacts yet")

    def test_should_say_that_no_alliance_is_configured(self):
        response = self.client.get(reverse("eos_spy_network:hostiles"))

        self.assertContains(response, "No Alliance is configured yet.")

    def test_should_say_that_no_source_is_ticked(self):
        configure()

        response = self.client.get(reverse("eos_spy_network:hostiles"))

        self.assertContains(response, "No contact source is ticked")

    def test_should_name_sources_without_contacts(self):
        configure()
        ContactSource.objects.create(kind=ContactSource.CORPORATION, entity_id=2001, name="Tokenless Corp")
        ContactSource.objects.create(kind=ContactSource.CORPORATION, entity_id=2002, name="Unread Corp")
        ContactSource.objects.create(kind=ContactSource.CORPORATION, entity_id=2003, name="Read Corp")
        add_token(ContactSource.CORPORATION, 2002, contacts_modified=False)
        add_token(ContactSource.CORPORATION, 2003)

        response = self.client.get(reverse("eos_spy_network:hostiles"))

        self.assertContains(response, "Tokenless Corp")
        self.assertContains(response, "Unread Corp")
        # case-sensitive: "Unread Corp" does not contain it
        self.assertNotContains(response, "Read Corp")

    def test_should_say_that_aa_contacts_is_missing(self):
        configure()

        with patch(NOT_INSTALLED, return_value=False):
            response = self.client.get(reverse("eos_spy_network:hostiles"))

        self.assertContains(response, "aa-contacts is not installed")


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
            {"alliance": make_alliance().pk, "hostile_below": "-5", "source": ["corporation:2002"]},
        )

        self.assertRedirects(response, reverse("eos_spy_network:settings"))
        self.assertEqual(list(ContactSource.objects.values_list("entity_id", flat=True)), [2002])
        self.assertEqual(SpyConfiguration.get_solo().hostile_below, Decimal("-5"))

    def test_should_reject_a_threshold_out_of_range(self):
        configure()

        response = self.client.post(
            reverse("eos_spy_network:settings"), {"alliance": make_alliance().pk, "hostile_below": "-11"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SpyConfiguration.get_solo().hostile_below, Decimal("0"))

    def test_should_render_without_aa_contacts(self):
        configure()

        with patch(NOT_INSTALLED, return_value=False):
            response = self.client.get(reverse("eos_spy_network:settings"))

        self.assertContains(response, "aa-contacts is not installed")
        self.assertNotContains(response, "Open aa-contacts")
