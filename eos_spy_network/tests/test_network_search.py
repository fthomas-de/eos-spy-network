from corptools.models import EveName

from django.urls import reverse
from django.utils import timezone

from eos_spy_network import snapshot
from eos_spy_network.models import ContactSource, SpyConfiguration

from . import test_network
from .base import ALLIANCE_ID, OTHER_ALLIANCE_ID, add_contact, add_token, configure, make_alliance, make_corporation, make_user

OUTSIDER = test_network.OUTSIDER
HOSTILE_CORP = test_network.HOSTILE_CORP
VIEW_SUSPECTS = "eos_spy_network.view_suspects"
MANAGE_SETTINGS = "eos_spy_network.manage_settings"


class SearchTestCase(test_network.NetworkTestCase):
    """An outsider in a Corporation the Alliance holds at -10, in a neutral Alliance; the alt trades with it."""

    def setUp(self):
        super().setUp()
        ContactSource.objects.create(kind=ContactSource.ALLIANCE, entity_id=ALLIANCE_ID, name="Us")
        add_token(ContactSource.ALLIANCE, ALLIANCE_ID)
        make_corporation(HOSTILE_CORP, alliance_id=OTHER_ALLIANCE_ID)
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, HOSTILE_CORP, -10)
        # the counterpart's name comes from corptools' names; a name only ESI knows shows as the ID
        EveName.objects.create(eve_id=OUTSIDER, name="Outsider", category="character")
        self.esi_names.return_value = {OUTSIDER: ("Outsider", "character")}
        self.esi_affiliations.return_value = {OUTSIDER: (HOSTILE_CORP, OTHER_ALLIANCE_ID)}
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")
        self.report = snapshot.Report(snapshot.update())


class TestSearch(SearchTestCase):
    def test_should_find_a_row_by_the_counterpart_its_corporation_or_its_alliance(self):
        for query in ("outsid", f"Corp {HOSTILE_CORP}", f"alliance {OTHER_ALLIANCE_ID}"):
            with self.subTest(query=query):
                (row,) = self.report.search(query)
                self.assertEqual(row["counterpart"], "Outsider")

    def test_should_name_the_main_and_its_corporation_for_the_link(self):
        (row,) = self.report.search("Outsider")

        self.assertEqual(
            (row["main_id"], row["main_name"], row["tile"].id), (self.main.character_id, self.main.character_name, 2001)
        )

    def test_should_not_search_the_own_characters(self):
        # the user's reading: the other side, not the account that made the row
        self.assertEqual(self.report.search(self.alt.character_name), [])

    def test_should_find_nothing_for_a_blank_or_unknown_text(self):
        self.assertEqual(self.report.search("   "), [])
        self.assertEqual(self.report.search("Nobody"), [])

    def test_should_find_a_party_by_its_id_and_not_by_a_longer_name(self):
        other = OUTSIDER + 1
        EveName.objects.create(eve_id=other, name="Outsider Two", category="character")
        self.esi_names.return_value = {OUTSIDER: ("Outsider", "character"), other: ("Outsider Two", "character")}
        self.esi_affiliations.return_value = {
            OUTSIDER: (HOSTILE_CORP, OTHER_ALLIANCE_ID),
            other: (HOSTILE_CORP, OTHER_ALLIANCE_ID),
        }
        self.pay(self.alt, other, ref_type="player_trading")
        report = snapshot.Report(snapshot.update())

        self.assertEqual(len(report.search("Outsider")), 2)
        self.assertEqual([row["counterpart"] for row in report.search("Outsider", OUTSIDER)], ["Outsider"])
        # a Corporation's ID finds every counterpart in it, whatever the name
        self.assertEqual(len(report.search("", HOSTILE_CORP)), 2)

    def test_should_offer_every_party_once_grouped_by_category(self):
        groups = [(str(label), names) for label, names in self.report.suggestions()]

        self.assertEqual(
            groups,
            [
                ("Character", ["Outsider"]),
                ("Corporation", [f"Corp {HOSTILE_CORP}"]),
                ("Alliance", [f"Alliance {OTHER_ALLIANCE_ID}"]),
            ],
        )


class TestSearchPage(SearchTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("lead", VIEW_SUSPECTS))

    def test_should_link_each_row_to_its_main_on_the_network_page(self):
        response = self.client.get(reverse("eos_spy_network:network_search"), {"q": "Outsider"})

        link = reverse("eos_spy_network:network_corporation", args=[2001])
        self.assertContains(response, f'href="{link}#main-{self.main.character_id}"')
        self.assertContains(response, 'selected>Outsider</option>', html=False)

    def test_should_show_the_age_of_the_own_character(self):
        self.alt.birthday = timezone.localdate().replace(year=timezone.localdate().year - 3, month=1, day=1)
        self.alt.save()

        response = self.client.get(reverse("eos_spy_network:network_search"), {"q": "Outsider"})

        self.assertContains(response, "<th>Age</th>")
        self.assertContains(response, f'title="{self.alt.birthday.isoformat()}"')

    def test_should_search_by_the_id_of_a_highlight_tile(self):
        # the ID decides: the name in the box is only shown
        response = self.client.get(reverse("eos_spy_network:network_search"), {"q": "Nobody", "id": OUTSIDER})

        self.assertNotContains(response, "Nothing in the Network matches.")
        self.assertContains(response, f'href="{reverse("eos_spy_network:network_corporation", args=[2001])}#main-')

    def test_should_ignore_an_id_that_is_no_number(self):
        response = self.client.get(reverse("eos_spy_network:network_search"), {"q": "Nobody", "id": "x"})

        self.assertContains(response, "Nothing in the Network matches.")

    def test_should_keep_a_typed_text_in_the_box(self):
        response = self.client.get(reverse("eos_spy_network:network_search"), {"q": "outs"})

        self.assertContains(response, '<option value="outs" selected>outs</option>', html=True)
        self.assertContains(response, "Outsider")

    def test_should_say_when_nothing_matches(self):
        response = self.client.get(reverse("eos_spy_network:network_search"), {"q": "Nobody"})

        self.assertContains(response, "Nothing in the Network matches.")

    def test_should_offer_the_search_to_viewers_only(self):
        self.client.force_login(make_user("nobody"))

        response = self.client.get(reverse("eos_spy_network:network_search"))

        self.assertEqual(response.status_code, 403)

    def test_should_put_the_search_box_on_the_network_page_and_not_in_the_menu(self):
        search = reverse("eos_spy_network:network_search")

        network = self.client.get(reverse("eos_spy_network:network"))
        markers = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(network, f'action="{search}"')
        self.assertContains(network, '<option value="Outsider">Outsider</option>', html=True)
        self.assertNotContains(markers, search)

    def test_should_keep_the_network_tab_current_on_the_search_page(self):
        response = self.client.get(reverse("eos_spy_network:network_search"), {"q": "Outsider"})

        self.assertEqual(response.context["nav"], "network")

    def test_should_not_offer_the_alliance_or_its_corporations(self):
        stored = snapshot.current()
        # a snapshot of before the rule: the outsider sits in our Corporation and Alliance
        row = next(row for row in stored.data["entities"] if row[0] == OUTSIDER)
        row[3], row[4] = 2001, ALLIANCE_ID

        parties = snapshot.Report(stored).parties

        self.assertIn(OUTSIDER, parties)
        self.assertNotIn(2001, parties)
        self.assertNotIn(ALLIANCE_ID, parties)


class TestHighlights(SearchTestCase):
    def tile(self, eve_id):
        return self.report.highlight_tiles({str(eve_id): "stored name"})[0]

    def test_should_tile_a_character_with_its_corporation_and_alliance(self):
        tile = self.tile(OUTSIDER)

        self.assertEqual((tile["name"], str(tile["label"]), tile["accounts"]), ("Outsider", "Character", 1))
        self.assertEqual(
            [(group["name"], str(group["label"])) for group in tile["groups"]],
            [(f"Corp {HOSTILE_CORP}", "Corporation"), (f"Alliance {OTHER_ALLIANCE_ID}", "Alliance")],
        )
        # the Alliance holds -10 for the Corporation only
        self.assertEqual(str(tile["groups"][0]["held"]), "-10.0")
        self.assertIsNone(tile["groups"][1]["held"])

    def test_should_tile_a_corporation_with_its_alliance_and_its_standing(self):
        tile = self.tile(HOSTILE_CORP)

        self.assertEqual((str(tile["label"]), tile["accounts"]), ("Corporation", 1))
        self.assertEqual(str(tile["hostile"]), "-10.0")
        self.assertEqual([group["name"] for group in tile["groups"]], [f"Alliance {OTHER_ALLIANCE_ID}"])

    def test_should_count_the_accounts_behind_an_alliance(self):
        self.assertEqual(self.tile(OTHER_ALLIANCE_ID)["accounts"], 1)

    def test_should_count_none_for_a_party_the_network_does_not_hold(self):
        # the stored name stands in: the party left the snapshot
        tile = self.tile(12345)

        self.assertEqual((tile["name"], tile["accounts"], tile["groups"]), ("stored name", 0, []))


class TestHighlightPages(SearchTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("lead", VIEW_SUSPECTS))

    def test_should_show_no_section_without_a_highlight(self):
        response = self.client.get(reverse("eos_spy_network:network"))

        self.assertNotContains(response, "Highlights")

    def test_should_show_the_tiles_above_the_corporations_of_the_network_page(self):
        configure(highlight_counterparts={str(OUTSIDER): "Outsider"})

        response = self.client.get(reverse("eos_spy_network:network"))

        html = response.content.decode()
        self.assertContains(response, reverse("eos_spy_network:network_search") + f"?q=Outsider&amp;id={OUTSIDER}")
        self.assertLess(html.index("Highlights"), html.index(reverse("eos_spy_network:network_corporation", args=[2001])))

    def test_should_not_show_the_tiles_on_the_markers_page(self):
        configure(highlight_counterparts={str(OUTSIDER): "Outsider"})

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertNotContains(response, "Highlights")
        self.assertNotContains(response, "?q=Outsider")


class TestHighlightSettings(SearchTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("admin", MANAGE_SETTINGS))

    def post(self, *highlights):
        return self.client.post(
            reverse("eos_spy_network:settings"),
            {
                "alliance": make_alliance().pk,
                "hostile_below": "0",
                "blue_from": "5",
                "network_blue_above": "0",
                "network_min_connections": "2",
                "min_kill_value": "0",
                "corp_changes_per_year": "4",
                "lookback_days": "365",
                "highlight_counterparts": list(highlights),
            },
        )

    def test_should_offer_the_parties_of_the_network_with_their_category(self):
        response = self.client.get(reverse("eos_spy_network:settings"))

        self.assertEqual(
            response.context["form"].fields["highlight_counterparts"].choices,
            [
                (str(OTHER_ALLIANCE_ID), f"Alliance {OTHER_ALLIANCE_ID} (Alliance)"),
                (str(HOSTILE_CORP), f"Corp {HOSTILE_CORP} (Corporation)"),
                (str(OUTSIDER), "Outsider (Character)"),
            ],
        )

    def test_should_keep_a_stored_highlight_that_left_the_network(self):
        configure(highlight_counterparts={"5": "Gone"})

        response = self.client.get(reverse("eos_spy_network:settings"))

        self.assertIn(("5", "Gone"), response.context["form"].fields["highlight_counterparts"].choices)

    def test_should_save_the_picked_parties_with_their_names(self):
        response = self.post(str(OUTSIDER), str(HOSTILE_CORP))

        self.assertRedirects(response, reverse("eos_spy_network:settings"))
        self.assertEqual(
            SpyConfiguration.get_solo().highlight_counterparts,
            {str(OUTSIDER): "Outsider", str(HOSTILE_CORP): f"Corp {HOSTILE_CORP}"},
        )

    def test_should_keep_the_stored_name(self):
        configure(highlight_counterparts={str(OUTSIDER): "Old name"})

        self.post(str(OUTSIDER))

        self.assertEqual(SpyConfiguration.get_solo().highlight_counterparts, {str(OUTSIDER): "Old name"})

    def test_should_refuse_a_party_the_network_does_not_hold(self):
        response = self.post("99")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SpyConfiguration.get_solo().highlight_counterparts, {})

    def test_should_take_a_highlight_back(self):
        configure(highlight_counterparts={str(OUTSIDER): "Outsider"})

        self.post()

        self.assertEqual(SpyConfiguration.get_solo().highlight_counterparts, {})
