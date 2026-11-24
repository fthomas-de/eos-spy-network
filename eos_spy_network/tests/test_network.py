import re
from datetime import timedelta

from corptools.models import (
    CharacterAudit,
    CharacterWalletJournalEntry,
    Contract,
    ContractItem,
    CorporationHistory,
    EveName,
)
from eve_sde.models import ItemCategory, ItemGroup, ItemType

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership

from eos_spy_network import markers, snapshot, tenure
from eos_spy_network.network import connections

from eos_spy_network.models import ContactSource, SpyConfiguration

from .base import (
    ALLIANCE_ID,
    OTHER_ALLIANCE_ID,
    SpyTestCase,
    add_contact,
    add_token,
    configure,
    make_character,
    make_corporation,
    make_user,
)

OUTSIDER = 90000100  # a character Auth has never seen
OTHER_OUTSIDER = 90000101
OUTSIDER_CORPORATION = 4100  # a Corporation outside the Alliance
NPC_CORPORATION = 1000125


class NetworkTestCase(SpyTestCase):
    def setUp(self):
        super().setUp()
        # most fixtures are one connection: the minimum is a rule of its own, see TestMinimumConnections
        configure(network_min_connections=1)
        make_corporation(2001)
        self.user = make_user("member")
        self.main = self.user.profile.main_character
        self.alt = make_character(5001)
        CharacterOwnership.objects.create(user=self.user, character=self.alt, owner_hash="hash-5001")
        self.audits = {
            character.character_id: CharacterAudit.objects.create(character=character)
            for character in (self.main, self.alt)
        }
        self.entry_id = 0

    def pay(self, character, counterpart_id, ref_type="player_donation", amount=100, days_ago=0, **extra):
        self.entry_id += 1
        CharacterWalletJournalEntry.objects.create(
            character=self.audits[character.character_id],
            entry_id=self.entry_id,
            date=timezone.now() - timedelta(days=days_ago),
            description="",
            ref_type=ref_type,
            first_party_id=character.character_id,
            second_party_id=counterpart_id,
            amount=-amount,
            balance=0,
            **extra,
        )

    def contract(
        self, character, partner_id, issued=True, days_ago=0, status="finished", items=False, availability="personal",
        acceptor=0, **isk
    ):
        """A contract of ``character`` with ``partner_id``, issued by the one or the other; ``items`` puts one in.

        ``acceptor`` is who took it; 0 (not accepted) by default.
        """
        self.entry_id += 1
        issuer, assignee = (character.character_id, partner_id) if issued else (partner_id, character.character_id)
        audit = self.audits[character.character_id]
        when = timezone.now() - timedelta(days=days_ago)
        contract = Contract.objects.create(
            id=f"{audit.pk}-{self.entry_id}", contract_id=self.entry_id, character=audit,
            issuer_id=issuer, issuer_name=eve_name(issuer),
            issuer_corporation_id=2001, issuer_corporation_name=eve_name(2001, "corporation"),
            assignee_id=assignee, assignee_name=eve_name(assignee), acceptor_id=acceptor, acceptor_name=eve_name(acceptor),
            for_corporation=False, date_expired=when, date_issued=when, status=status,
            contract_type="item_exchange", availability=availability, title="", **isk,
        )
        if items:
            category = ItemCategory.objects.get_or_create(id=6, defaults={"name": "Ship", "published": True})[0]
            group, _created = ItemGroup.objects.get_or_create(
                id=25, defaults={"name": "Frigate", "category": category, "published": True}
            )
            item_type = ItemType.objects.get_or_create(id=587, defaults={"name": "Rifter", "group": group})[0]
            ContractItem.objects.create(
                contract=contract, is_included=True, is_singleton=False, quantity=1, record_id=self.entry_id,
                type_name=item_type,
            )
        return contract

    def account(self, since=None, minimum=1):
        return connections({self.user.pk: self.main}, ALLIANCE_ID, since=since, minimum=minimum).get(self.user.pk)

    def make_hostile(self, eve_id, contact_type="character", standing=-10):
        if not ContactSource.objects.exists():
            ContactSource.objects.create(kind=ContactSource.ALLIANCE, entity_id=ALLIANCE_ID, name="Us")
            add_token(ContactSource.ALLIANCE, ALLIANCE_ID)
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, eve_id, standing, contact_type=contact_type)

    def stored_accounts(self):
        tile = snapshot.Report(snapshot.update()).network_tile(2001)
        return tile.accounts


class TestSharedCounterpart(NetworkTestCase):
    def test_should_connect_main_and_alt_paying_the_same_outsider(self):
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)

        account = self.account()

        self.assertEqual(account.shared, {OUTSIDER})
        self.assertEqual({link.character_id for link in account.links}, {self.main.character_id, 5001})

    def test_should_connect_two_alts_and_draw_the_main_with_them(self):
        other_alt = make_character(5002)
        CharacterOwnership.objects.create(user=self.user, character=other_alt, owner_hash="hash-5002")
        self.audits[5002] = CharacterAudit.objects.create(character=other_alt)
        self.pay(self.alt, OUTSIDER)
        self.pay(other_alt, OUTSIDER)

        account = self.account()
        graph = account.graph()

        self.assertEqual(account.shared, {OUTSIDER})
        # the main paid nothing but anchors the account in the graph
        self.assertIn(self.main.character_id, {node["id"] for node in graph["nodes"]})
        accounts = {(edge["from"], edge["to"]) for edge in graph["edges"] if edge["kind"] == "account"}
        self.assertEqual(accounts, {(self.main.character_id, 5001), (self.main.character_id, 5002)})

    def test_should_count_two_payments_of_one_character(self):
        self.pay(self.main, OUTSIDER)
        self.pay(self.main, OUTSIDER)

        self.assertEqual(self.account().counterparts, {OUTSIDER: str(OUTSIDER)})

    def test_should_count_contract_payments(self):
        self.pay(self.main, OUTSIDER, ref_type="contract_price")
        self.pay(self.alt, OUTSIDER, ref_type="contract_reward")

        self.assertEqual(self.account().shared, {OUTSIDER})

    def test_should_ignore_other_journal_entries(self):
        self.pay(self.main, OUTSIDER, ref_type="skill_purchase")
        self.pay(self.alt, OUTSIDER, ref_type="market_transaction")

        self.assertIsNone(self.account())

    def test_should_ignore_members_of_the_alliance(self):
        member = make_character(6001)
        self.pay(self.main, member.character_id)
        self.pay(self.alt, member.character_id)

        self.assertIsNone(self.account())

    def test_should_ignore_npcs(self):
        self.pay(self.main, NPC_CORPORATION)
        self.pay(self.alt, NPC_CORPORATION)

        self.assertIsNone(self.account())


class TestSettingsFilters(NetworkTestCase):
    """Time frame and ignored types reach the network through the snapshot."""

    def setUp(self):
        super().setUp()
        self.make_hostile(OUTSIDER)

    def test_should_ignore_payments_before_the_time_frame(self):
        configure(lookback_days=30, network_min_connections=2)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER, days_ago=60)

        self.assertEqual(self.stored_accounts(), [])

    def test_should_take_every_payment_with_a_time_frame_of_0(self):
        configure(lookback_days=0)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER, days_ago=3000)

        self.assertEqual(len(self.stored_accounts()), 1)

    def test_should_ignore_the_configured_types(self):
        configure(ignored_ref_types=["player_trading"])
        self.pay(self.main, OUTSIDER, ref_type="player_trading")

        self.assertEqual(self.stored_accounts(), [])


class TestIgnoredCharacters(NetworkTestCase):
    def add_alt(self, character_id, **where):
        alt = make_character(character_id, **where)
        CharacterOwnership.objects.create(user=self.user, character=alt, owner_hash=f"hash-{character_id}")
        self.audits[character_id] = CharacterAudit.objects.create(character=alt)
        return alt

    def account(self, *ignored):
        return connections(
            {self.user.pk: self.main}, ALLIANCE_ID, ignored_characters=set(ignored), minimum=2
        ).get(self.user.pk)

    def test_should_leave_out_the_payments_of_an_ignored_character(self):
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)

        # the outsider is shared by two characters only until one of them is ignored
        self.assertIsNone(self.account(5001))

    def test_should_keep_the_partner_the_other_characters_share(self):
        third = self.add_alt(5002)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)
        self.pay(third, OUTSIDER)

        account = self.account(5001)

        self.assertEqual(account.shared, {OUTSIDER})
        self.assertEqual({link.character_id for link in account.links}, {self.main.character_id, 5002})

    def test_should_not_take_an_ignored_own_character_for_an_outsider(self):
        # outside the Alliance, so only the ownership says it is no outsider
        third = self.add_alt(5002)
        self.add_alt(5003, corporation_id=3001, alliance_id=None)
        self.pay(self.main, 5003)
        self.pay(third, 5003)

        self.assertIsNone(self.account(5003))

    def test_should_reach_the_network_through_the_settings(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)
        configure(ignored_network_characters=[5001], network_min_connections=2)

        self.assertEqual(self.stored_accounts(), [])

    def test_should_not_touch_the_network_with_the_contact_list(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)
        configure(ignored_contact_characters=[5001])

        self.assertEqual(len(self.stored_accounts()), 1)


class TestIgnoredCounterparts(NetworkTestCase):
    def account(self, *ignored):
        return connections(
            {self.user.pk: self.main}, ALLIANCE_ID, ignored_counterparts=set(ignored)
        ).get(self.user.pk)

    def test_should_leave_an_ignored_counterpart_out_of_the_shared_rule(self):
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)

        self.assertIsNone(self.account(OUTSIDER))

    def test_should_leave_an_ignored_counterpart_out_of_player_trading(self):
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        self.assertIsNone(self.account(OUTSIDER))

    def test_should_keep_the_other_counterparts(self):
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)
        self.pay(self.main, OTHER_OUTSIDER)
        self.pay(self.alt, OTHER_OUTSIDER)

        self.assertEqual(self.account(OUTSIDER).shared, {OTHER_OUTSIDER})

    def test_should_reach_the_network_through_the_settings(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)
        # the stored keys are strings: JSON has no other
        configure(ignored_network_counterparts={str(OUTSIDER): "Stranger"})

        self.assertEqual(self.stored_accounts(), [])


class TestPlayerTrading(NetworkTestCase):
    def test_should_show_a_single_trade_with_an_outsider(self):
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        account = self.account()

        self.assertEqual(account.trading, {OUTSIDER})
        self.assertEqual(account.shared, set())

    def test_should_ignore_a_trade_inside_the_alliance(self):
        member = make_character(6001)
        self.pay(self.alt, member.character_id, ref_type="player_trading")

        self.assertIsNone(self.account())


class TestNames(NetworkTestCase):
    def test_should_take_the_name_from_corptools(self):
        EveName.objects.create(eve_id=OUTSIDER, name="Stranger", category="character")
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        self.assertEqual(self.account().counterparts, {OUTSIDER: "Stranger"})

    def test_should_fall_back_to_the_id(self):
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        self.assertEqual(self.account().counterparts, {OUTSIDER: str(OUTSIDER)})


class TestPeriod(NetworkTestCase):
    def test_should_keep_the_first_and_the_last_payment(self):
        self.pay(self.main, OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)
        first = CharacterWalletJournalEntry.objects.get(entry_id=1)
        first.date = timezone.now() - timedelta(days=40)
        first.save()

        link = next(link for link in self.account().links if link.character_id == self.main.character_id)

        self.assertEqual(link.first, first.date.date().isoformat())
        self.assertEqual(link.last, timezone.now().date().isoformat())


class TestHostileOnly(NetworkTestCase):
    def test_should_drop_a_shared_partner_that_is_not_hostile(self):
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)

        self.assertEqual(self.stored_accounts(), [])

    def test_should_drop_a_trade_with_a_partner_that_is_not_hostile(self):
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        self.assertEqual(self.stored_accounts(), [])

    def test_should_keep_only_the_hostile_partners_of_an_account(self):
        self.make_hostile(OUTSIDER)
        for character in (self.main, self.alt):
            self.pay(character, OUTSIDER)
            self.pay(character, OTHER_OUTSIDER)

        (account,) = self.stored_accounts()

        self.assertEqual(set(account.counterparts), {OUTSIDER})
        self.assertEqual({link.counterpart_id for link in account.links}, {OUTSIDER})


class TestSnapshot(NetworkTestCase):
    def test_should_restore_the_connections_from_the_stored_json(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        (account,) = self.stored_accounts()

        self.assertEqual(account.shared, {OUTSIDER})
        self.assertEqual(account.trading, {OUTSIDER})
        self.assertEqual({link.last for link in account.links}, {timezone.now().date().isoformat()})
        graph = account.graph()
        self.assertEqual(
            {node["id"]: (node["group"], node["level"]) for node in graph["nodes"]},
            {self.main.character_id: ("main", 0), 5001: ("alt", 1), OUTSIDER: ("hostile_partner", 2)},
        )
        self.assertEqual(
            sorted(edge["kind"] for edge in graph["edges"]), ["account", "payment", "trading"]
        )

    def test_should_store_the_metrics(self):
        self.pay(self.main, OUTSIDER)

        metrics = snapshot.Report(snapshot.update()).metrics

        self.assertEqual(metrics["journal_entries"], 1)
        self.assertEqual(metrics["characters"], 2)
        self.assertGreater(metrics["queries"], 0)

    def test_should_drop_the_snapshot_without_an_alliance(self):
        snapshot.update()
        configure(alliance_id=None)

        self.assertIsNone(snapshot.update())
        self.assertIsNone(snapshot.current())


HOSTILE_CORP = 98000500


class TestHostileChain(NetworkTestCase):
    """An outsider in a Corporation the Alliance holds at -10, in a neutral Alliance."""

    def setUp(self):
        super().setUp()
        ContactSource.objects.create(kind=ContactSource.ALLIANCE, entity_id=ALLIANCE_ID, name="Us")
        add_token(ContactSource.ALLIANCE, ALLIANCE_ID)
        make_corporation(HOSTILE_CORP, alliance_id=OTHER_ALLIANCE_ID)
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, HOSTILE_CORP, -10)
        # Auth has never seen the outsider: its Corporation comes from ESI
        self.esi_names.return_value = {OUTSIDER: ("Outsider", "character")}
        self.esi_affiliations.return_value = {OUTSIDER: (HOSTILE_CORP, OTHER_ALLIANCE_ID)}
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

    def account(self):
        (account,) = snapshot.Report(snapshot.update()).network_tile(2001).accounts
        return account

    def test_should_follow_the_partner_to_its_hostile_corporation(self):
        graph = self.account().graph()

        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(nodes[OUTSIDER]["group"], "hostile_partner")
        self.assertEqual(nodes[HOSTILE_CORP]["group"], "hostile_corporation")
        self.assertEqual(nodes[HOSTILE_CORP]["standing"], "-10.0")
        self.assertEqual(nodes[HOSTILE_CORP]["sources"], [["Us", "-10.0"]])
        self.assertEqual([nodes[OUTSIDER]["level"], nodes[HOSTILE_CORP]["level"]], [2, 3])
        # the neutral Alliance behind the reason gets no node, only a line in the partner's tooltip
        self.assertNotIn(OTHER_ALLIANCE_ID, nodes)
        self.assertEqual(nodes[OUTSIDER]["affiliation"], [f"Corp {HOSTILE_CORP}", f"Alliance {OTHER_ALLIANCE_ID}"])
        members = {(edge["from"], edge["to"]) for edge in graph["edges"] if edge["kind"] == "member"}
        self.assertEqual(members, {(OUTSIDER, HOSTILE_CORP)})

    def test_should_keep_the_corporation_between_partner_and_hostile_alliance(self):
        self.esi_affiliations.return_value = {OUTSIDER: (4001, OTHER_ALLIANCE_ID)}
        self.make_hostile(OTHER_ALLIANCE_ID, contact_type="alliance")

        graph = self.account().graph()

        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(nodes[4001]["group"], "corporation")
        self.assertEqual(nodes[OTHER_ALLIANCE_ID]["group"], "hostile_alliance")
        members = {(edge["from"], edge["to"]) for edge in graph["edges"] if edge["kind"] == "member"}
        self.assertEqual(members, {(OUTSIDER, 4001), (4001, OTHER_ALLIANCE_ID)})

    def test_should_colour_a_highlighted_alliance_like_a_hostile_one(self):
        account = self.account()
        account.hostiles = {}
        account.highlights = frozenset({OTHER_ALLIANCE_ID})

        nodes = {node["id"]: node["group"] for node in account.graph()["nodes"]}

        self.assertEqual(nodes[OUTSIDER], "hostile_partner")
        self.assertEqual(nodes[HOSTILE_CORP], "corporation")
        self.assertEqual(nodes[OTHER_ALLIANCE_ID], "hostile_alliance")

    def test_should_draw_no_group_of_a_partner_hostile_itself(self):
        self.esi_affiliations.return_value = {OUTSIDER: (4001, OTHER_ALLIANCE_ID)}
        self.make_hostile(OUTSIDER)

        nodes = {node["id"] for node in self.account().graph()["nodes"]}

        self.assertEqual(nodes, {self.main.character_id, 5001, OUTSIDER})

    def test_should_name_corporation_and_alliance_in_the_table(self):
        (row,) = self.account().rows

        self.assertTrue(row["hostile"])
        self.assertEqual(row["corporation"]["name"], f"Corp {HOSTILE_CORP}")
        self.assertEqual(str(row["corporation"]["standing"]), "-10.0")
        self.assertIsNone(row["alliance"]["standing"])

    def test_should_hold_the_standing_of_the_alliance_for_every_party_of_the_row(self):
        # neither is hostile: the table shows them all the same
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, OTHER_ALLIANCE_ID, 5, contact_type="alliance")
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, OUTSIDER, 2, contact_type="character")

        (row,) = self.account().rows

        self.assertEqual(str(row["counterpart_held"]), "2.0")
        self.assertEqual(str(row["corporation"]["held"]), "-10.0")
        self.assertEqual(str(row["alliance"]["held"]), "5.0")

    def test_should_hold_none_for_a_party_the_alliance_has_no_contact_with(self):
        (row,) = self.account().rows

        self.assertIsNone(row["counterpart_held"])
        self.assertIsNone(row["alliance"]["held"])

    def test_should_leave_the_standings_of_a_corporation_source_out(self):
        # a Corporation's private contact is not what the Alliance holds
        ContactSource.objects.create(kind=ContactSource.CORPORATION, entity_id=2001, name="Corp")
        add_token(ContactSource.CORPORATION, 2001)
        add_contact(ContactSource.CORPORATION, 2001, OUTSIDER, -5, contact_type="character")

        (row,) = self.account().rows

        self.assertIsNone(row["counterpart_held"])

    def test_should_show_none_for_a_snapshot_without_standings(self):
        stored = snapshot.update()
        del stored.data["standings"]

        (account,) = snapshot.Report(stored).network_tile(2001).accounts

        self.assertIsNone(account.rows[0]["corporation"]["held"])

    def test_should_count_the_hostile_partner_on_the_tile(self):
        tile = snapshot.Report(snapshot.update()).network_tile(2001)

        self.assertEqual(tile.hostile_count, 1)

    def test_should_drop_a_partner_in_a_neutral_corporation(self):
        self.esi_affiliations.return_value = {OUTSIDER: (4001, None)}

        self.assertEqual(self.stored_accounts(), [])


def eve_name(eve_id, category="character"):
    return EveName.objects.get_or_create(eve_id=eve_id, defaults={"name": f"Name {eve_id}", "category": category})[0]


class TestContractsWithoutIsk(NetworkTestCase):
    """A gift of items leaves no journal entry with the partner; the contract stands in as a payment."""

    def test_should_count_a_contract_without_isk_as_a_payment(self):
        self.contract(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)

        account = self.account()

        self.assertEqual(account.shared, {OUTSIDER})
        link = next(link for link in account.links if link.character_id == self.main.character_id)
        self.assertEqual((link.payments, link.trades, link.isk), (1, 0, 0))

    def test_should_count_both_directions_and_every_status(self):
        self.contract(self.main, OUTSIDER, status="outstanding")
        self.contract(self.alt, OUTSIDER, issued=False, status="deleted")

        self.assertEqual(self.account().shared, {OUTSIDER})

    def test_should_leave_a_contract_with_isk_to_the_journal(self):
        for isk in ({"price": 1}, {"reward": 1}, {"collateral": 1}):
            with self.subTest(**isk):
                Contract.objects.all().delete()
                self.contract(self.main, OUTSIDER, **isk)
                self.contract(self.alt, OUTSIDER, **isk)

                self.assertIsNone(self.account())

    def test_should_count_each_contract_as_a_payment(self):
        self.contract(self.main, OUTSIDER)
        self.contract(self.main, OUTSIDER)

        (link,) = self.account().links

        self.assertEqual(link.points, 2)

    def test_should_ignore_a_contract_before_the_time_frame(self):
        self.contract(self.main, OUTSIDER)
        self.contract(self.alt, OUTSIDER, days_ago=60)

        self.assertIsNone(self.account(since=timezone.now() - timedelta(days=30), minimum=2))


class TestPrivateContracts(NetworkTestCase):
    """A private contract with items is a kind of its own: it shows an account alone and is no 0-ISK payment."""

    def test_should_show_an_account_for_one_private_contract_with_items(self):
        self.contract(self.alt, OUTSIDER, items=True)

        account = self.account()

        self.assertEqual(account.contracting, {OUTSIDER})
        self.assertEqual(account.shared, set())
        (link,) = account.links
        self.assertEqual((link.contracts, link.payments, link.isk), (1, 0, 0))

    def test_should_count_it_with_isk_too(self):
        self.contract(self.alt, OUTSIDER, items=True, price=1000)

        self.assertEqual(self.account().contracting, {OUTSIDER})

    def test_should_leave_a_contract_without_items_a_payment(self):
        self.contract(self.main, OUTSIDER)
        self.contract(self.alt, OUTSIDER)

        account = self.account()

        self.assertEqual(account.contracting, set())
        self.assertEqual(account.shared, {OUTSIDER})

    def test_should_ignore_a_contract_inside_the_alliance(self):
        member = make_character(6001)
        self.contract(self.alt, member.character_id, items=True)

        self.assertIsNone(self.account())

    def test_should_keep_to_the_time_frame(self):
        self.contract(self.alt, OUTSIDER, items=True, days_ago=40)

        self.assertIsNone(self.account(since=timezone.now() - timedelta(days=10)))

    def test_should_show_a_line_of_its_own_in_the_graph(self):
        self.contract(self.alt, OUTSIDER, items=True)

        edges = [edge for edge in self.account().graph()["edges"] if edge["kind"] != "account"]

        (edge,) = edges
        self.assertEqual((edge["kind"], edge["contracts"], edge["payments"]), ("contract", 1, 0))

    def test_should_keep_it_through_the_snapshot(self):
        self.make_hostile(OUTSIDER)
        self.contract(self.alt, OUTSIDER, items=True)

        (account,) = self.stored_accounts()

        self.assertEqual(account.contracting, {OUTSIDER})
        self.assertEqual(account.rows[0]["contracts"], 1)


class TestPublicContracts(NetworkTestCase):
    """Whoever takes a public contract is a stranger on the market: neither the contract nor its ISK counts."""

    def test_should_ignore_a_public_contract(self):
        for items in (False, True):
            with self.subTest(items=items):
                Contract.objects.all().delete()
                self.contract(self.main, OUTSIDER, items=items, availability="public")

                self.assertIsNone(self.account())

    def test_should_ignore_the_payment_of_a_public_contract(self):
        contract = self.contract(self.main, OUTSIDER, availability="public", price=1000, acceptor=OUTSIDER)
        self.pay(
            self.main, OUTSIDER, ref_type="contract_price", context_id_type="contract_id",
            context_id=contract.contract_id,
        )

        self.assertIsNone(self.account())

    def test_should_ignore_it_issued_before_the_time_frame(self):
        contract = self.contract(self.main, OUTSIDER, availability="public", price=1000, days_ago=40)
        self.pay(
            self.main, OUTSIDER, ref_type="contract_price", context_id_type="contract_id",
            context_id=contract.contract_id,
        )

        self.assertIsNone(self.account(since=timezone.now() - timedelta(days=30)))

    def test_should_keep_the_payment_of_a_private_contract(self):
        contract = self.contract(self.main, OUTSIDER, price=1000)
        self.pay(
            self.main, OUTSIDER, ref_type="contract_price", context_id_type="contract_id",
            context_id=contract.contract_id,
        )

        (link,) = self.account().links
        self.assertEqual(link.payments, 1)


class TestContractParty(NetworkTestCase):
    """A contract counts for one party: the acceptor once accepted, before that the assignee."""

    def test_should_count_the_acceptor_only(self):
        self.contract(self.main, OUTSIDER_CORPORATION, items=True, acceptor=OUTSIDER)

        (link,) = self.account().links
        self.assertEqual((link.counterpart_id, link.points), (OUTSIDER, 1))

    def test_should_count_the_assignee_before_it_is_accepted(self):
        self.contract(self.main, OUTSIDER_CORPORATION, items=True, status="outstanding")

        (link,) = self.account().links
        self.assertEqual(link.counterpart_id, OUTSIDER_CORPORATION)


class TestDirection(NetworkTestCase):
    """The arrow of the graph: "o" went from the own character, "i" came to it."""

    def direction(self):
        (link,) = self.account().links
        return link.direction

    def test_should_point_away_from_a_character_that_paid(self):
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        self.assertEqual(self.direction(), "o")

    def test_should_point_to_a_character_that_was_paid(self):
        self.pay(self.alt, OUTSIDER, ref_type="player_trading", amount=-100)

        self.assertEqual(self.direction(), "i")

    def test_should_point_both_ways_for_both(self):
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")
        self.pay(self.alt, OUTSIDER, ref_type="player_trading", amount=-100)

        self.assertEqual(self.direction(), "io")

    def test_should_follow_the_issuer_of_a_contract(self):
        self.contract(self.alt, OUTSIDER, items=True, issued=True)
        self.assertEqual(self.direction(), "o")

        Contract.objects.all().delete()
        self.contract(self.alt, OUTSIDER, items=True, issued=False)
        self.assertEqual(self.direction(), "i")

    def test_should_reach_the_graph_edges_and_survive_the_snapshot(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        (account,) = self.stored_accounts()

        (edge,) = [edge for edge in account.graph()["edges"] if edge["kind"] == "trading"]
        self.assertEqual(edge["direction"], "o")

    def test_should_read_an_older_snapshot_without_direction(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")
        stored = snapshot.update()
        for corporation in stored.data["corporations"]:
            for stored_account in corporation.get("connections", []):
                # the links of 0.0.43 and older end with the period
                stored_account["links"] = [link[:7] for link in stored_account["links"]]

        (account,) = snapshot.Report(stored).network_tile(2001).accounts

        self.assertEqual([(link.contracts, link.direction) for link in account.links], [(0, "")])


class TestAge(NetworkTestCase):
    def rows(self):
        from eos_spy_network.network import fill_birthdays

        account = self.account()
        fill_birthdays([account])
        return account.rows

    def test_should_give_the_age_of_the_own_character_in_days(self):
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")
        self.alt.birthday = timezone.localdate() - timedelta(days=400)
        self.alt.save()

        (row,) = self.rows()

        self.assertEqual((row["character_id"], row["age_days"], row["birthday"]), (5001, 400, self.alt.birthday))

    def test_should_leave_the_age_empty_without_a_birthday(self):
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        (row,) = self.rows()

        self.assertEqual((row["birthday"], row["age_days"]), (None, None))

    def test_should_read_the_birthdays_in_one_query(self):
        from eos_spy_network.network import fill_birthdays

        self.pay(self.main, OUTSIDER, ref_type="player_trading")
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")
        account = self.account()

        with self.assertNumQueries(1):
            fill_birthdays([account])


class TestNeutralPartners(NetworkTestCase):
    """The switch lets neutral partners stay; a blue one goes unless its chain holds a hostile."""

    def setUp(self):
        super().setUp()
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)

    def in_hostile_corporation(self):
        make_corporation(HOSTILE_CORP, alliance_id=OTHER_ALLIANCE_ID)
        self.esi_names.return_value = {OUTSIDER: ("Outsider", "character")}
        self.esi_affiliations.return_value = {OUTSIDER: (HOSTILE_CORP, OTHER_ALLIANCE_ID)}

    def test_should_keep_a_neutral_partner_when_switched_on(self):
        configure(network_neutral=True)

        (account,) = self.stored_accounts()

        self.assertEqual(set(account.counterparts), {OUTSIDER})
        self.assertEqual(account.hostile, set())

    def test_should_drop_a_blue_partner(self):
        configure(network_neutral=True)
        self.make_hostile(OUTSIDER, standing=0.5)

        self.assertEqual(self.stored_accounts(), [])

    def test_should_take_the_blue_standing_from_the_settings(self):
        configure(network_neutral=True, network_blue_above=5)
        self.make_hostile(OUTSIDER, standing=5)

        self.assertEqual(len(self.stored_accounts()), 1)

    def test_should_drop_a_partner_blue_through_its_corporation(self):
        configure(network_neutral=True)
        self.in_hostile_corporation()
        self.make_hostile(HOSTILE_CORP, contact_type="corporation", standing=10)

        self.assertEqual(self.stored_accounts(), [])

    def test_should_keep_a_blue_partner_in_a_hostile_corporation(self):
        configure(network_neutral=True)
        self.in_hostile_corporation()
        self.make_hostile(OUTSIDER, standing=10)
        self.make_hostile(HOSTILE_CORP, contact_type="corporation", standing=-10)

        (account,) = self.stored_accounts()

        self.assertEqual(account.hostile, {OUTSIDER})


def _from(table):
    """Matches a query that reads ``table`` first, in MySQL's and sqlite's quoting."""
    return re.compile(rf'FROM [`"]?{table}[`"]?\s', re.IGNORECASE)


CORPTOOLS_DATA = re.compile(
    r'FROM [`"]?corptools_(characterwalletjournalentry|mailmessage|mailmessage_recipients|contract|'
    r'charactercontact|corporationhistory)[`"]?\s',
    re.IGNORECASE,
)


class TestQueries(NetworkTestCase):
    """The big corptools tables are read by audit ID, and what both calculations need is read once."""

    def setUp(self):
        super().setUp()
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)

    def test_should_read_the_network_journal_without_characters_or_names(self):
        with CaptureQueriesContext(connection) as queries:
            self.account()

        corptools = [query["sql"] for query in queries if CORPTOOLS_DATA.search(query["sql"])]
        # the journal, and the contracts without ISK
        self.assertEqual(len(corptools), 2)
        for sql in corptools:
            self.assertNotIn("eveonline_evecharacter", sql)
            self.assertNotIn("corptools_evename", sql)

    def test_should_read_the_marker_tables_without_eve_characters(self):
        with CaptureQueriesContext(connection) as queries:
            (tile,) = markers.corporation_tiles(corporation_id=2001)

        self.assertEqual(tile.suspects[0].markers[markers.WALLET].count, 2)
        corptools = [query["sql"] for query in queries if CORPTOOLS_DATA.search(query["sql"])]
        # history, contacts, two for mails, wallet, contracts
        self.assertEqual(len(corptools), 6)
        for sql in corptools:
            self.assertNotIn("eveonline_evecharacter", sql)

    def test_should_read_hostiles_mains_and_characters_once_per_run(self):
        with CaptureQueriesContext(connection) as queries:
            snapshot.build(SpyConfiguration.get_solo())

        def count(table):
            return sum(1 for query in queries if _from(table).search(query["sql"]))

        # once for the hostiles, once for the blues of the blue kills, once for the Network's standings
        self.assertEqual(count("aa_contacts_alliancecontact"), 3)
        self.assertEqual(count("authentication_userprofile"), 1)
        # the characters, and inside the mains' query the accounts with an alt in the Alliance
        self.assertEqual(count("authentication_characterownership"), 2)


class TestTenure(NetworkTestCase):
    """The main was in a Corporation outside the Alliance until 30 days ago; the alt was always in 2001."""

    def setUp(self):
        super().setUp()
        for corporation_id, days_ago, record_id in ((4000, 100, 1), (2001, 30, 2)):
            name, _created = EveName.objects.get_or_create(
                eve_id=corporation_id, defaults={"name": f"Corp {corporation_id}", "category": "corporation"}
            )
            CorporationHistory.objects.create(
                character=self.audits[self.main.character_id], corporation_id=corporation_id,
                corporation_name=name, record_id=record_id, start_date=timezone.now() - timedelta(days=days_ago),
            )
        # 4000 was never in the Alliance, 2001 was for years
        self.esi_alliance_history.side_effect = lambda corporation_id: (
            [] if corporation_id == 4000 else [["2020-01-01T00:00:00+00:00", ALLIANCE_ID]]
        )
        config = SpyConfiguration.get_solo()
        self.tenure = tenure.load(config, markers.roster(config).characters)

    def account(self, counted=True, minimum=1):
        return connections(
            {self.user.pk: self.main}, ALLIANCE_ID, tenure=self.tenure if counted else None, minimum=minimum
        ).get(self.user.pk)

    def test_should_not_count_a_payment_of_the_main_from_before_it_joined(self):
        self.pay(self.main, OUTSIDER, days_ago=60)
        self.pay(self.alt, OUTSIDER, days_ago=60)

        # two points only when both payments count
        self.assertIsNotNone(self.account(counted=False, minimum=2))
        self.assertIsNone(self.account(minimum=2))

    def test_should_count_a_payment_of_the_main_from_since_it_joined(self):
        self.pay(self.main, OUTSIDER, days_ago=10)
        self.pay(self.alt, OUTSIDER, days_ago=60)

        self.assertEqual(self.account().shared, {OUTSIDER})

    def test_should_not_count_a_private_contract_from_before_the_joining(self):
        self.contract(self.main, OUTSIDER, days_ago=60, items=True)

        self.assertIsNotNone(self.account(counted=False))
        self.assertIsNone(self.account())

    def test_should_count_a_private_contract_from_since_the_joining(self):
        self.contract(self.main, OUTSIDER, days_ago=10, items=True)

        self.assertEqual(self.account().contracting, {OUTSIDER})

    def test_should_not_count_a_contract_without_isk_from_before_the_joining(self):
        self.contract(self.main, OUTSIDER, days_ago=60)
        self.contract(self.alt, OUTSIDER, days_ago=60)

        self.assertIsNotNone(self.account(counted=False, minimum=2))
        self.assertIsNone(self.account(minimum=2))

    def test_should_apply_it_in_the_calculation(self):
        configure(network_min_connections=2)
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER, days_ago=60)
        self.pay(self.alt, OUTSIDER, days_ago=60)

        self.assertEqual(snapshot.Report(snapshot.update()).network_tile(2001).accounts, [])

    def test_should_apply_it_to_the_markers_of_the_calculation(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER, days_ago=60)

        tile = snapshot.Report(snapshot.update()).tile(2001)
        self.assertEqual(tile.suspects, [])

        self.pay(self.main, OUTSIDER, days_ago=10)

        (suspect,) = snapshot.Report(snapshot.update()).tile(2001).suspects
        self.assertEqual(suspect.markers[markers.WALLET].count, 1)


class TestOwnAlliance(NetworkTestCase):
    """A character Auth has never seen, whom ESI puts into the Alliance, is a member and no counterpart."""

    def test_should_drop_a_partner_that_esi_puts_into_our_corporation(self):
        configure(network_neutral=True)
        self.esi_names.return_value = {OUTSIDER: ("Outsider", "character")}
        self.esi_affiliations.return_value = {OUTSIDER: (2001, ALLIANCE_ID)}
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        self.assertEqual(snapshot.Report(snapshot.update()).network_tile(2001).accounts, [])

    def test_should_drop_a_partner_that_esi_puts_into_our_alliance_only(self):
        configure(network_neutral=True)
        self.esi_names.return_value = {OUTSIDER: ("Outsider", "character")}
        self.esi_affiliations.return_value = {OUTSIDER: (4001, ALLIANCE_ID)}
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        self.assertEqual(snapshot.Report(snapshot.update()).network_tile(2001).accounts, [])

    def test_should_keep_a_neutral_partner_of_another_alliance(self):
        configure(network_neutral=True)
        self.esi_names.return_value = {OUTSIDER: ("Outsider", "character")}
        self.esi_affiliations.return_value = {OUTSIDER: (4001, OTHER_ALLIANCE_ID)}
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        (account,) = snapshot.Report(snapshot.update()).network_tile(2001).accounts

        self.assertEqual(account.trading, {OUTSIDER})
        self.assertEqual(account.entities[OUTSIDER].alliance_id, OTHER_ALLIANCE_ID)


def _corptools_history(audit, *records):
    """corptools' Corporation history of ``audit``: (Corporation ID, days ago) oldest first."""
    for record_id, (corporation_id, days_ago) in enumerate(records, start=1):
        name, _created = EveName.objects.get_or_create(
            eve_id=corporation_id, defaults={"name": f"Corp {corporation_id}", "category": "corporation"}
        )
        CorporationHistory.objects.create(
            character=audit, corporation_id=corporation_id, corporation_name=name, record_id=record_id,
            start_date=timezone.now() - timedelta(days=days_ago),
        )


def _days_ago(days):
    return (timezone.now() - timedelta(days=days)).isoformat()


class TestCounterpartTenure(NetworkTestCase):
    """A counterpart counts by where it was at the time, not by where it is today (user, 2026-11-24)."""

    def test_should_count_a_member_of_today_for_the_time_before_it_joined(self):
        other = make_user("other").profile.main_character
        _corptools_history(CharacterAudit.objects.create(character=other), (4000, 100), (2001, 30))
        config = SpyConfiguration.get_solo()
        found = tenure.load(config, markers.roster(config).characters)

        def account():
            return connections({self.user.pk: self.main}, ALLIANCE_ID, tenure=found).get(self.user.pk)

        self.pay(self.alt, other.character_id, ref_type="player_trading", days_ago=10)
        self.assertIsNone(account())

        self.pay(self.alt, other.character_id, ref_type="player_trading", days_ago=60)
        self.assertEqual(account().trading, {other.character_id})
        self.assertEqual(account().links[0].payments, 1)

    def test_should_drop_a_hostile_for_the_time_it_was_in_the_alliance(self):
        # hostile through its Corporation only, which Auth does not know: the markers never see it
        self.make_hostile(4000, contact_type="corporation")
        self.esi_names.return_value = {OUTSIDER: ("Outsider", "character")}
        self.esi_affiliations.return_value = {OUTSIDER: (4000, None)}
        self.esi_corporation_history.return_value = [[_days_ago(200), 2001], [_days_ago(40), 4000]]
        self.pay(self.main, OUTSIDER, days_ago=60)
        self.pay(self.alt, OUTSIDER, days_ago=60)

        self.assertEqual(self.stored_accounts(), [])

        self.pay(self.main, OUTSIDER, days_ago=10)
        self.pay(self.alt, OUTSIDER, days_ago=10)

        (account,) = self.stored_accounts()
        self.assertEqual(account.shared, {OUTSIDER})
        self.assertEqual(account.links[0].payments, 1)

    def test_should_keep_a_neutral_partner_auth_has_in_the_alliance_for_the_time_before_it_joined(self):
        configure(network_neutral=True)
        make_character(OTHER_OUTSIDER, corporation_id=2001)
        self.esi_corporation_history.return_value = [[_days_ago(100), 4000], [_days_ago(20), 2001]]
        self.pay(self.alt, OTHER_OUTSIDER, ref_type="player_trading", days_ago=10)

        self.assertEqual(self.stored_accounts(), [])

        self.pay(self.alt, OTHER_OUTSIDER, ref_type="player_trading", days_ago=60)

        (account,) = self.stored_accounts()
        self.assertEqual(account.trading, {OTHER_OUTSIDER})


class TestMinimumConnections(NetworkTestCase):
    """Every connection is one point; an account shows up at ``network_min_connections`` with one party (user, 2026-11-24)."""

    def setUp(self):
        super().setUp()
        configure(network_min_connections=2)

    def in_corporation(self, corporation_id, *outsiders):
        make_corporation(corporation_id, alliance_id=OTHER_ALLIANCE_ID)
        self.esi_names.return_value = {eve_id: (f"Outsider {eve_id}", "character") for eve_id in outsiders}
        self.esi_affiliations.return_value = {eve_id: (corporation_id, OTHER_ALLIANCE_ID) for eve_id in outsiders}

    def test_should_not_show_one_connection(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER)

        self.assertEqual(self.stored_accounts(), [])

    def test_should_not_show_one_trade_or_one_private_contract(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")
        self.assertEqual(self.stored_accounts(), [])

        self.contract(self.alt, OTHER_OUTSIDER, items=True)
        self.make_hostile(OTHER_OUTSIDER)
        self.assertEqual(self.stored_accounts(), [])

    def test_should_show_two_connections_of_one_character(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.main, OUTSIDER)

        (account,) = self.stored_accounts()

        self.assertEqual(set(account.counterparts), {OUTSIDER})

    def test_should_add_up_every_kind_of_connection(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")
        self.contract(self.alt, OUTSIDER, items=True)
        self.contract(self.main, OUTSIDER)

        (account,) = self.stored_accounts()

        self.assertEqual(sum(link.points for link in account.links), 4)

    def test_should_add_up_the_characters_of_the_account(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)

        self.assertEqual(len(self.stored_accounts()), 1)

    def test_should_count_a_private_contract_with_isk_once(self):
        contract = self.contract(self.alt, OUTSIDER, items=True, price=1000)
        self.pay(
            self.alt, OUTSIDER, ref_type="contract_price", amount=1000,
            context_id=contract.contract_id, context_id_type="contract_id",
        )

        (link,) = self.account().links

        # the ISK of the wallet entry still shows, it is just no second connection
        self.assertEqual((link.points, link.contracts, link.payments, link.isk), (1, 1, 0, 1000))
        self.assertIsNone(self.account(minimum=2))

    def test_should_not_reach_the_minimum_with_one_contract_to_a_corporation(self):
        # assigned to the hostile Corporation, taken by its member: one point for the group, not one each
        self.in_corporation(OUTSIDER_CORPORATION, OUTSIDER)
        self.make_hostile(OUTSIDER_CORPORATION, contact_type="corporation")
        self.contract(self.main, OUTSIDER_CORPORATION, items=True, acceptor=OUTSIDER)

        self.assertEqual(self.stored_accounts(), [])

    def test_should_count_the_wallet_entry_of_another_contract(self):
        contract = self.contract(self.alt, OUTSIDER, items=True)
        self.pay(
            self.alt, OUTSIDER, ref_type="contract_price", context_id=contract.contract_id + 1000,
            context_id_type="contract_id",
        )

        self.assertEqual(self.account().links[0].points, 2)

    def test_should_not_show_a_partner_that_is_not_hostile(self):
        self.pay(self.main, OUTSIDER)
        self.pay(self.main, OUTSIDER)

        self.assertEqual(self.stored_accounts(), [])

    def test_should_follow_the_setting(self):
        self.make_hostile(OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.main, OUTSIDER)
        configure(network_min_connections=3)

        self.assertEqual(self.stored_accounts(), [])

        self.pay(self.main, OUTSIDER)

        self.assertEqual(len(self.stored_accounts()), 1)

    def test_should_add_up_the_members_of_a_hostile_corporation(self):
        self.in_corporation(HOSTILE_CORP, OUTSIDER, OTHER_OUTSIDER)
        self.make_hostile(HOSTILE_CORP, contact_type="corporation")
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OTHER_OUTSIDER)

        (account,) = self.stored_accounts()

        # both rows stay, the one connection of each included: they are what added up
        self.assertEqual(set(account.counterparts), {OUTSIDER, OTHER_OUTSIDER})
        self.assertEqual(len(account.links), 2)

    def test_should_not_add_up_two_different_corporations(self):
        other_corporation = HOSTILE_CORP + 1
        self.in_corporation(HOSTILE_CORP, OUTSIDER)
        make_corporation(other_corporation, alliance_id=OTHER_ALLIANCE_ID)
        self.esi_names.return_value[OTHER_OUTSIDER] = ("Other", "character")
        self.esi_affiliations.return_value[OTHER_OUTSIDER] = (other_corporation, OTHER_ALLIANCE_ID)
        self.make_hostile(HOSTILE_CORP, contact_type="corporation")
        self.make_hostile(other_corporation, contact_type="corporation")
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OTHER_OUTSIDER)

        self.assertEqual(self.stored_accounts(), [])

    def test_should_add_up_the_members_of_a_hostile_alliance(self):
        self.esi_names.return_value = {OUTSIDER: ("One", "character"), OTHER_OUTSIDER: ("Two", "character")}
        self.esi_affiliations.return_value = {OUTSIDER: (4001, OTHER_ALLIANCE_ID), OTHER_OUTSIDER: (4002, OTHER_ALLIANCE_ID)}
        self.make_hostile(OTHER_ALLIANCE_ID, contact_type="alliance")
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OTHER_OUTSIDER)

        self.assertEqual(len(self.stored_accounts()), 1)

    def test_should_leave_a_neutral_corporation_no_group_unless_neutral_partners_are_on(self):
        self.in_corporation(4001, OUTSIDER, OTHER_OUTSIDER)
        self.make_hostile(OUTSIDER)
        self.make_hostile(OTHER_OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OTHER_OUTSIDER)

        self.assertEqual(self.stored_accounts(), [])

        configure(network_neutral=True)

        self.assertEqual(len(self.stored_accounts()), 1)

    def test_should_leave_a_blue_corporation_no_group(self):
        configure(network_neutral=True)
        # no Alliance behind it: a neutral one would be a group of its own
        self.esi_names.return_value = {eve_id: (f"Outsider {eve_id}", "character") for eve_id in (OUTSIDER, OTHER_OUTSIDER)}
        self.esi_affiliations.return_value = {OUTSIDER: (4001, None), OTHER_OUTSIDER: (4001, None)}
        self.make_hostile(OUTSIDER)
        self.make_hostile(OTHER_OUTSIDER)
        self.make_hostile(4001, contact_type="corporation", standing=10)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OTHER_OUTSIDER)

        self.assertEqual(self.stored_accounts(), [])

    def test_should_not_count_a_highlight_as_a_group(self):
        self.in_corporation(4001, OUTSIDER, OTHER_OUTSIDER)
        self.make_hostile(OUTSIDER)
        self.make_hostile(OTHER_OUTSIDER)
        configure(highlight_counterparts={"4001": "Corp 4001"})
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OTHER_OUTSIDER)

        self.assertEqual(self.stored_accounts(), [])
