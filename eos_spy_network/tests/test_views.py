from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from eos_spy_network import snapshot
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
            reverse("eos_spy_network:network"),
            reverse("eos_spy_network:network_corporation", args=[2001]),
            reverse("eos_spy_network:rebuild"),
            reverse("eos_spy_network:settings"),
        ):
            with self.subTest(url):
                response = self.client.get(url)
                self.assertTrue(response.url.startswith(LOGIN))

    def test_should_keep_settings_from_viewers(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:settings"))

        self.assertTrue(response.url.startswith(LOGIN))

    def test_should_keep_the_network_from_viewers_without_view_evidence(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

        for url in (reverse("eos_spy_network:network"), reverse("eos_spy_network:network_corporation", args=[2001])):
            with self.subTest(url):
                response = self.client.get(url)
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
        snapshot.update()


class TestCorporationsPage(SuspectPageTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

    def test_should_show_a_tile_per_corporation(self):
        make_corporation(2002)
        snapshot.update()

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, reverse("eos_spy_network:corporation", args=[2001]))
        self.assertContains(response, reverse("eos_spy_network:corporation", args=[2002]))
        self.assertContains(response, "Hostile membership")
        self.assertNotContains(response, "No contacts in aa-contacts yet")

    def test_should_offer_to_hide_corporations_without_markers(self):
        make_corporation(2002)
        snapshot.update()

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "data-eos-spy-network-hide-clean")
        # only the clean tile of 2002 is marked for hiding, not the one with the suspect
        self.assertContains(response, "data-eos-spy-network-clean", count=1)

    def test_should_show_the_metrics_in_the_footer(self):
        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "Last calculation")
        self.assertContains(response, "wallet entries")
        self.assertContains(response, reverse("eos_spy_network:rebuild"))

    def test_should_say_that_nothing_is_calculated_yet(self):
        snapshot.current().delete()

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "Not calculated yet.")
        self.assertNotContains(response, "Last calculation")

    def test_should_not_show_the_result_of_another_alliance(self):
        configure(alliance_id=3999)

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "Not calculated yet.")

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
        self.assertEqual(
            [suspect.main.character_id for suspect in response.context["tile"].suspects],
            [self.suspect_main.character_id],
        )

    def test_should_refuse_a_corporation_outside_the_alliance(self):
        make_corporation(2999, alliance_id=None)

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2999]))

        self.assertEqual(response.status_code, 404)


class TestEvidence(SuspectPageTestCase):
    # the wallet entry's counterpart alone; the membership marker names "Char 5001: Bad Corp"
    COUNTERPART = ">Bad Corp</td>"

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
        snapshot.update()

    def test_should_hide_the_counterparts_without_view_evidence(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, "ISK with hostiles")
        self.assertNotContains(response, self.COUNTERPART)

    def test_should_show_the_counterparts_with_view_evidence(self):
        self.client.force_login(make_user("lead", VIEW_SUSPECTS, VIEW_EVIDENCE))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, self.COUNTERPART)
        self.assertContains(response, "<th>Alliance</th>", html=True)
        self.assertContains(response, "player donation")
        self.assertContains(response, timezone.now().date().isoformat())


class TestCorporationChangesTooltip(SuspectPageTestCase):
    def test_should_name_the_corporations_joined_in_the_tooltip(self):
        from corptools.models import CharacterAudit, CorporationHistory, EveName

        configure(corp_changes_per_year=2)
        audit = CharacterAudit.objects.create(character=EveCharacter.objects.get(pk=self.suspect_main.pk))
        for record_id, name in enumerate(("First Corp", "Second Corp"), 1):
            CorporationHistory.objects.create(
                character=audit,
                corporation_id=1000000 + record_id,
                corporation_name=EveName.objects.create(eve_id=1000000 + record_id, name=name, category="corporation"),
                record_id=record_id,
                start_date=timezone.now(),
            )
        snapshot.update()
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        today = timezone.now().date().isoformat()
        self.assertContains(
            response,
            f'<abbr title="{today} First Corp&#10;{today} Second Corp">{self.suspect_main.character_name}: 2</abbr>',
            html=False,
        )


class TestRebuild(SuspectPageTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

    def test_should_queue_the_task_and_return_to_the_page(self):
        page = reverse("eos_spy_network:corporation", args=[2001])

        response = self.client.post(reverse("eos_spy_network:rebuild"), {"next": page})

        self.assertRedirects(response, page)
        self.update_snapshot.delay.assert_called_once_with()

    def test_should_not_follow_a_foreign_next(self):
        response = self.client.post(reverse("eos_spy_network:rebuild"), {"next": "https://example.com/"})

        self.assertRedirects(response, reverse("eos_spy_network:index"), fetch_redirect_response=False)

    def test_should_refuse_get(self):
        response = self.client.get(reverse("eos_spy_network:rebuild"))

        self.assertEqual(response.status_code, 405)
        self.update_snapshot.delay.assert_not_called()


class TestNetworkPages(SuspectPageTestCase):
    OUTSIDER = 90000100

    def setUp(self):
        super().setUp()
        from corptools.models import CharacterAudit, CharacterWalletJournalEntry, EveName

        EveName.objects.create(eve_id=self.OUTSIDER, name="Stranger", category="character")
        main = EveCharacter.objects.get(pk=self.suspect_main.pk)
        CharacterWalletJournalEntry.objects.create(
            character=CharacterAudit.objects.create(character=main),
            entry_id=1,
            date=timezone.now(),
            description="",
            ref_type="player_trading",
            first_party_id=main.character_id,
            second_party_id=self.OUTSIDER,
            amount=-1000,
            balance=0,
        )
        # only a hostile partner makes the account show up
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, self.OUTSIDER, -10, contact_type="character")
        snapshot.update()
        self.client.force_login(make_user("lead", VIEW_SUSPECTS, VIEW_EVIDENCE))

    def test_should_show_a_tile_per_corporation(self):
        response = self.client.get(reverse("eos_spy_network:network"))

        self.assertContains(response, reverse("eos_spy_network:network_corporation", args=[2001]))
        self.assertContains(response, "Player trading")

    def test_should_offer_to_hide_corporations_without_connections(self):
        make_corporation(2002)
        snapshot.update()

        response = self.client.get(reverse("eos_spy_network:network"))

        self.assertContains(response, 'data-eos-spy-network-hide-clean="network"')
        # only the tile without connections is marked for the switch
        self.assertContains(response, "data-eos-spy-network-clean", count=1)
        self.assertContains(response, "eos_spy_network/js/tiles.")

    def test_should_list_the_mains_and_keep_their_graphs_for_the_click(self):
        response = self.client.get(reverse("eos_spy_network:network_corporation", args=[2001]))

        main_id = self.suspect_main.character_id
        self.assertContains(response, f'data-eos-spy-network-show="{main_id}"')
        self.assertContains(response, f'class="card d-none" data-eos-spy-network-account="{main_id}"')
        self.assertContains(response, "data-eos-spy-network-placeholder")
        self.assertContains(response, "Stranger")
        self.assertContains(response, "data-eos-spy-network-graph")
        self.assertContains(response, "vis-network.min.js")
        self.assertContains(response, f'<td data-order="{timezone.now().date().isoformat()}" class="text-nowrap">')

    def test_should_refuse_a_corporation_outside_the_alliance(self):
        response = self.client.get(reverse("eos_spy_network:network_corporation", args=[2999]))

        self.assertEqual(response.status_code, 404)


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
                "lookback_days": "90",
                "ignored_ref_types": ["market_transaction", "player_trading"],
                "source": ["corporation:2002"],
            },
        )

        self.assertRedirects(response, reverse("eos_spy_network:settings"))
        # the stored result belongs to the old settings
        self.update_snapshot.delay.assert_called_once_with()
        self.assertEqual(list(ContactSource.objects.values_list("entity_id", flat=True)), [2002])
        config = SpyConfiguration.get_solo()
        self.assertEqual(config.hostile_below, Decimal("-5"))
        self.assertEqual(config.corp_changes_per_year, 6)
        self.assertEqual(config.lookback_days, 90)
        self.assertEqual(config.ignored_ref_types, ["market_transaction", "player_trading"])

    def test_should_offer_the_types_of_the_wallet_journal(self):
        from corptools.models import CharacterAudit, CharacterWalletJournalEntry

        configure()
        CharacterWalletJournalEntry.objects.create(
            character=CharacterAudit.objects.create(character=make_character(5001)),
            entry_id=1,
            date=timezone.now(),
            description="",
            ref_type="bounty_prizes",
            amount=1,
            balance=1,
        )

        response = self.client.get(reverse("eos_spy_network:settings"))

        self.assertContains(response, '<option value="bounty_prizes">bounty prizes</option>', html=True)
        self.assertContains(
            response, '<option value="market_transaction" selected>market transaction</option>', html=True
        )

    def test_should_reject_an_unknown_type(self):
        configure()

        response = self.client.post(
            reverse("eos_spy_network:settings"),
            {
                "alliance": make_alliance().pk,
                "hostile_below": "0",
                "corp_changes_per_year": "4",
                "lookback_days": "365",
                "ignored_ref_types": ["no_such_type"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SpyConfiguration.get_solo().ignored_ref_types, ["market_transaction"])

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
