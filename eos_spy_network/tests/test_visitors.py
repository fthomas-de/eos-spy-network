"""Visitors: an account with an alt in a Corporation whose main is elsewhere (user, 2026-11-19).

Its whole account shows on the alt's Corporation page as well, to the
leadership and to that Corporation's CEO, read only; a main outside the
Alliance is checked at all only through such an alt.
"""

from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter

from eos_spy_network import api, snapshot
from eos_spy_network.auth_hooks import SpyNetworkMenuItem
from eos_spy_network.models import ContactSource

from .base import ALLIANCE_ID, OTHER_ALLIANCE_ID, add_contact, make_character, make_corporation, make_user
from .test_views import HOSTILE_CORP, MANAGE_SETTINGS, VIEW_SUSPECTS, SuspectPageTestCase

VIEW_OWN_CORPORATION = "eos_spy_network.view_own_corporation"
BLOCK = "Alts of mains in other Corporations"


def add_alt(user, character_id, corporation_id, alliance_id=ALLIANCE_ID):
    alt = make_character(character_id, corporation_id=corporation_id, alliance_id=alliance_id)
    CharacterOwnership.objects.create(user=user, character=alt, owner_hash=f"hash-{character_id}")
    return alt


class VisitorTestCase(SuspectPageTestCase):
    """Besides the suspect of 2001: "spy" (main in 2002) and "outsider" (main outside the Alliance), each with
    an alt in 2001 and one in the hostile Corporation."""

    def setUp(self):
        super().setUp()
        make_corporation(2002)
        self.spy = make_user("spy", corporation_id=2002)
        add_alt(self.spy, 5101, 2001)
        add_alt(self.spy, 5102, HOSTILE_CORP, alliance_id=None)
        self.outsider = make_user("outsider", corporation_id=2900, alliance_id=OTHER_ALLIANCE_ID)
        add_alt(self.outsider, 5201, 2001)
        add_alt(self.outsider, 5202, HOSTILE_CORP, alliance_id=None)
        snapshot.update()

    def page(self, corporation_id=2001):
        return self.client.get(reverse("eos_spy_network:corporation", args=[corporation_id]))

    def login(self, *perms, corporation_id=2001):
        self.client.force_login(make_user("viewer", *perms, corporation_id=corporation_id))


class TestCorporationPage(VisitorTestCase):
    def test_should_list_the_visitors_whole_accounts(self):
        self.login(VIEW_SUSPECTS)

        response = self.page()

        self.assertContains(response, BLOCK)
        for text in ("spy main", "Corp 2002", "Char 5101", "Char 5102", "outsider main", "Corp 2900", "Char 5202"):
            with self.subTest(text):
                self.assertContains(response, text)

    def test_should_count_the_visitors_in_the_head(self):
        self.login(VIEW_SUSPECTS)

        self.assertContains(self.page(), "Alts of other mains with markers: 2")

    def test_should_link_the_mains_corporation_page_for_the_leadership_only_inside_the_alliance(self):
        self.login(VIEW_SUSPECTS)

        response = self.page()

        self.assertContains(response, reverse("eos_spy_network:corporation", args=[2002]))
        self.assertNotContains(response, reverse("eos_spy_network:corporation", args=[2900]))

    def test_should_not_list_a_main_of_the_own_corporation_as_visitor(self):
        self.login(VIEW_SUSPECTS)

        response = self.page(2002)

        self.assertContains(response, "spy main")
        self.assertNotContains(response, BLOCK)

    def test_should_show_the_ceo_the_whole_account_without_the_link(self):
        self.client.force_login(make_user("ceo", VIEW_OWN_CORPORATION))

        response = self.page()

        self.assertContains(response, "Char 5102")
        self.assertContains(response, "Char 5202")
        self.assertNotContains(response, reverse("eos_spy_network:corporation", args=[2002]))


class TestReadOnly(VisitorTestCase):
    def setUp(self):
        super().setUp()
        from corptools.models import CharacterAudit, CharacterContact

        from .test_markers import eve_name

        audit = CharacterAudit.objects.create(character=EveCharacter.objects.get(character_id=5102))
        CharacterContact.objects.create(
            id=51020, character=audit, contact_id=HOSTILE_CORP, contact_type="corporation",
            contact_name=eve_name(HOSTILE_CORP, "corporation"), standing=5,
        )
        snapshot.update()
        self.main_id = self.spy.profile.main_character.character_id
        self.login(VIEW_SUSPECTS)

    def test_should_show_the_finding_without_its_controls(self):
        response = self.page()

        self.assertContains(response, "Friendly to hostiles")
        self.assertNotContains(response, f'data-eos-spy-network-kill-main="{self.main_id}"')

    def test_should_keep_the_controls_on_the_mains_own_page(self):
        self.assertContains(self.page(2002), f'data-eos-spy-network-kill-main="{self.main_id}"')


class TestCorporationsPage(VisitorTestCase):
    def test_should_count_the_visitors_on_the_tile(self):
        self.login(VIEW_SUSPECTS)

        response = self.client.get(reverse("eos_spy_network:corporations"))

        # one line per tile: 2001 and 2002
        self.assertContains(response, "Alts of other mains with markers: <span", count=2)

    def test_should_not_call_a_corporation_with_a_marked_visitor_clean(self):
        make_corporation(2003)
        add_alt(self.outsider, 5203, 2003)
        snapshot.update()
        self.login(VIEW_SUSPECTS)

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertNotContains(response, "data-eos-spy-network-clean")


class TestMenuCount(VisitorTestCase):
    def count(self, user):
        request = RequestFactory().get("/")
        request.user = user
        item = SpyNetworkMenuItem()
        item.render(request)
        return item.count

    def test_should_count_the_visitors_for_the_ceo(self):
        self.assertEqual(self.count(make_user("ceo", VIEW_OWN_CORPORATION)), 3)

    def test_should_count_each_account_once_for_the_leadership(self):
        self.assertEqual(self.count(make_user("lead", VIEW_SUSPECTS)), 3)


class TestApi(VisitorTestCase):
    def test_should_give_the_ceo_the_visitors_characters(self):
        found = api.character_markers(corporation_id=2001)

        self.assertIn(5102, found)
        self.assertIn(5202, found)

    def test_should_give_the_whole_alliance_the_outsider(self):
        self.assertIn(5202, api.character_markers())


class TestContracts(VisitorTestCase):
    def test_should_open_the_popup_of_a_visitors_main_for_the_ceo(self):
        from corptools.models import CharacterAudit, CharacterWalletJournalEntry

        main = EveCharacter.objects.get(pk=self.spy.profile.main_character.pk)
        CharacterWalletJournalEntry.objects.create(
            character=CharacterAudit.objects.create(character=main), entry_id=1, date=timezone.now(),
            description="", ref_type="contract_price", first_party_id=HOSTILE_CORP,
            second_party_id=main.character_id, amount=1000, balance=1, context_id=77,
            context_id_type="contract_id",
        )
        snapshot.update()
        self.client.force_login(make_user("ceo", VIEW_OWN_CORPORATION))

        response = self.client.get(reverse("eos_spy_network:contracts", args=[main.character_id, HOSTILE_CORP]))

        self.assertContains(response, "Contract 77")


class TestNetwork(VisitorTestCase):
    STRANGER = 90000100

    def trade(self, character):
        from corptools.models import CharacterAudit, CharacterWalletJournalEntry, EveName

        EveName.objects.create(eve_id=self.STRANGER, name="Stranger", category="character")
        CharacterWalletJournalEntry.objects.create(
            character=CharacterAudit.objects.create(character=character), entry_id=1, date=timezone.now(),
            description="", ref_type="player_trading", first_party_id=character.character_id,
            second_party_id=self.STRANGER, amount=-1000, balance=0,
        )
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, self.STRANGER, -10, contact_type="character")
        snapshot.update()
        self.login(VIEW_SUSPECTS)
        return self.client.get(reverse("eos_spy_network:network_corporation", args=[2001]))

    def test_should_show_an_outsider_at_the_alts_corporation(self):
        # the alt in the Alliance made the payment: the main outside the Alliance did nothing that counts
        response = self.trade(EveCharacter.objects.get(character_id=5201))

        self.assertContains(response, "outsider main")

    def test_should_not_count_what_the_main_outside_the_alliance_paid(self):
        response = self.trade(EveCharacter.objects.get(pk=self.outsider.profile.main_character.pk))

        self.assertNotContains(response, "outsider main")


class TestSettings(VisitorTestCase):
    def test_should_review_a_contact_of_an_outsider_in_the_settings(self):
        from corptools.models import CharacterAudit, CharacterContact

        from .test_markers import eve_name

        audit = CharacterAudit.objects.create(character=EveCharacter.objects.get(character_id=5202))
        CharacterContact.objects.create(
            id=52020, character=audit, contact_id=HOSTILE_CORP, contact_type="corporation",
            contact_name=eve_name(HOSTILE_CORP, "corporation"), standing=5,
        )
        snapshot.update()
        self.login(VIEW_SUSPECTS, MANAGE_SETTINGS)

        response = self.client.post(
            reverse("eos_spy_network:finding_note"),
            {
                "kind": "contacts",
                "main_id": self.outsider.profile.main_character.character_id,
                "key": f"{HOSTILE_CORP}:5",
                "cleared": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
