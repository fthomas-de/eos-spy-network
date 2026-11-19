"""view_own_corporation: the suspects and evidence of the main's own Corporation, nothing else."""

from django.test import RequestFactory
from django.urls import reverse

from eos_spy_network import snapshot
from eos_spy_network.auth_hooks import SpyNetworkMenuItem

from . import test_views
from .base import make_corporation, make_user
from .test_views import LOGIN, SuspectPageTestCase


VIEW_OWN_CORPORATION = "eos_spy_network.view_own_corporation"


class TestOwnCorporation(SuspectPageTestCase):
    """The suspect's main is in Corporation 2001; the CEO's main as well, unless said otherwise."""

    def setUp(self):
        super().setUp()
        make_corporation(2002)
        snapshot.update()

    def login(self, corporation_id=2001, *perms):
        user = make_user("ceo", VIEW_OWN_CORPORATION, *perms, corporation_id=corporation_id)
        self.client.force_login(user)
        return user

    def test_should_send_the_ceo_to_their_corporation(self):
        self.login()

        response = self.client.get(reverse("eos_spy_network:index"))

        self.assertRedirects(
            response, reverse("eos_spy_network:corporation", args=[2001]), fetch_redirect_response=False
        )

    def test_should_show_the_own_corporation(self):
        self.login()

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, "Hostile membership")
        self.assertContains(response, self.suspect_main.character_name)

    def test_should_not_show_another_corporation(self):
        self.login(2002)

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertEqual(response.status_code, 404)

    def test_should_keep_the_alliance_wide_pages_closed(self):
        self.login()

        for url in (
            reverse("eos_spy_network:corporations"),
            reverse("eos_spy_network:network"),
            reverse("eos_spy_network:network_corporation", args=[2001]),
            reverse("eos_spy_network:rebuild"),
            reverse("eos_spy_network:settings"),
            reverse("eos_spy_network:kill_note"),
            reverse("eos_spy_network:finding_note"),
            reverse("eos_spy_network:kill_day_note"),
        ):
            with self.subTest(url):
                self.assertTrue(self.client.get(url).url.startswith(LOGIN))

    def test_should_offer_neither_recalculation_nor_the_way_back_to_all_tiles(self):
        self.login()

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertNotContains(response, f'action="{reverse("eos_spy_network:rebuild")}"')
        self.assertNotContains(response, f'href="{reverse("eos_spy_network:corporations")}"')

    def test_should_let_the_ceo_follow_a_running_recalculation(self):
        # progress.js polls it on the Corporation page; a redirect to the login page would break the bar
        self.login()

        response = self.client.get(reverse("eos_spy_network:rebuild_progress"))

        self.assertEqual(response.json(), {"running": False})


class TestOwnCorporationEvidence(SuspectPageTestCase):
    # through the module: an imported TestCase class would run its tests here a second time
    add_donation = test_views.TestEvidence.add_donation
    COUNTERPART = test_views.TestEvidence.COUNTERPART

    def setUp(self):
        super().setUp()
        self.add_donation()

    def test_should_show_the_evidence_of_the_own_corporation(self):
        self.client.force_login(make_user("ceo", VIEW_OWN_CORPORATION))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, self.COUNTERPART)


class TestOwnCorporationContracts(SuspectPageTestCase):
    add_audit = test_views.TestContractDetails.add_audit
    pay = test_views.TestContractDetails.pay

    def setUp(self):
        super().setUp()
        self.add_audit()

    def test_should_show_the_contracts_of_the_own_corporation(self):
        self.pay(1, "contract_price", context_id=77)
        snapshot.update()
        self.client.force_login(make_user("ceo", VIEW_OWN_CORPORATION))

        self.assertContains(self.client.get(self.url), "Contract 77")

    def test_should_not_show_the_contracts_of_another_corporation(self):
        self.pay(1, "contract_price", context_id=77)
        snapshot.update()
        make_corporation(2002)
        self.client.force_login(make_user("ceo", VIEW_OWN_CORPORATION, corporation_id=2002))

        self.assertEqual(self.client.get(self.url).status_code, 404)


class TestOwnCorporationMenu(SuspectPageTestCase):
    def render(self, user):
        request = RequestFactory().get("/")
        request.user = user
        item = SpyNetworkMenuItem()
        return item, item.render(request)

    def test_should_count_the_mains_of_the_own_corporation(self):
        item, html = self.render(make_user("ceo", VIEW_OWN_CORPORATION))

        self.assertNotEqual(html, "")
        self.assertEqual(item.count, 1)

    def test_should_not_count_the_mains_of_other_corporations(self):
        make_corporation(2002)
        snapshot.update()

        item, _ = self.render(make_user("ceo", VIEW_OWN_CORPORATION, corporation_id=2002))

        self.assertEqual(item.count, 0)
