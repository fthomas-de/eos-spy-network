import re
from datetime import timedelta

from corptools.models import CharacterAudit, CharacterWalletJournalEntry, EveName

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership

from eos_spy_network import markers, snapshot
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
NPC_CORPORATION = 1000125


class NetworkTestCase(SpyTestCase):
    def setUp(self):
        super().setUp()
        configure()
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

    def pay(self, character, counterpart_id, ref_type="player_donation", amount=100, days_ago=0):
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
        )

    def account(self):
        return connections({self.user.pk: self.main}, ALLIANCE_ID).get(self.user.pk)

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

    def test_should_leave_an_outsider_paid_by_one_character_out(self):
        self.pay(self.main, OUTSIDER)
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OTHER_OUTSIDER)

        self.assertIsNone(self.account())

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
        configure(lookback_days=30)
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

    def test_should_count_the_hostile_partner_on_the_tile(self):
        tile = snapshot.Report(snapshot.update()).network_tile(2001)

        self.assertEqual(tile.hostile_count, 1)

    def test_should_drop_a_partner_in_a_neutral_corporation(self):
        self.esi_affiliations.return_value = {OUTSIDER: (4001, None)}

        self.assertEqual(self.stored_accounts(), [])


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

        journal = [query["sql"] for query in queries if CORPTOOLS_DATA.search(query["sql"])]
        self.assertEqual(len(journal), 1)
        self.assertNotIn("eveonline_evecharacter", journal[0])
        self.assertNotIn("corptools_evename", journal[0])

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

        self.assertEqual(count("aa_contacts_alliancecontact"), 1)
        self.assertEqual(count("authentication_userprofile"), 1)
        self.assertEqual(count("authentication_characterownership"), 1)
