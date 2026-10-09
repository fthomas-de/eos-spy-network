from corptools.models import CharacterAudit, CharacterWalletJournalEntry, EveName

from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership

from eos_spy_network import snapshot
from eos_spy_network.network import connections

from eos_spy_network.models import ContactSource

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

    def pay(self, character, counterpart_id, ref_type="player_donation", amount=100):
        self.entry_id += 1
        CharacterWalletJournalEntry.objects.create(
            character=self.audits[character.character_id],
            entry_id=self.entry_id,
            date=timezone.now(),
            description="",
            ref_type=ref_type,
            first_party_id=character.character_id,
            second_party_id=counterpart_id,
            amount=-amount,
            balance=0,
        )

    def account(self):
        return connections({self.user.pk: self.main}, ALLIANCE_ID).get(self.user.pk)


class TestSharedCounterpart(NetworkTestCase):
    def test_should_connect_main_and_alt_paying_the_same_outsider(self):
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER)

        account = self.account()

        self.assertEqual(account.shared, {OUTSIDER})
        self.assertEqual({link.character_id for link in account.links}, {self.main.character_id, 5001})

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


class TestSnapshot(NetworkTestCase):
    def test_should_restore_the_connections_from_the_stored_json(self):
        self.pay(self.main, OUTSIDER)
        self.pay(self.alt, OUTSIDER, ref_type="player_trading")

        report = snapshot.Report(snapshot.update())

        (account,) = report.network_tile(2001).accounts
        self.assertEqual(account.shared, {OUTSIDER})
        self.assertEqual(account.trading, {OUTSIDER})
        graph = account.graph()
        self.assertEqual(
            {node["id"]: (node["group"], node["level"]) for node in graph["nodes"]},
            {self.main.character_id: ("main", 0), 5001: ("alt", 1), OUTSIDER: ("partner", 2)},
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
        self.assertEqual(nodes[OTHER_ALLIANCE_ID]["group"], "alliance")
        self.assertEqual(
            [nodes[OUTSIDER]["level"], nodes[HOSTILE_CORP]["level"], nodes[OTHER_ALLIANCE_ID]["level"]], [2, 3, 4]
        )
        members = {(edge["from"], edge["to"]) for edge in graph["edges"] if edge["kind"] == "member"}
        self.assertEqual(members, {(OUTSIDER, HOSTILE_CORP), (HOSTILE_CORP, OTHER_ALLIANCE_ID)})

    def test_should_name_corporation_and_alliance_in_the_table(self):
        (row,) = self.account().rows

        self.assertTrue(row["hostile"])
        self.assertEqual(row["corporation"]["name"], f"Corp {HOSTILE_CORP}")
        self.assertEqual(str(row["corporation"]["standing"]), "-10.0")
        self.assertIsNone(row["alliance"]["standing"])

    def test_should_count_the_hostile_partner_on_the_tile(self):
        tile = snapshot.Report(snapshot.update()).network_tile(2001)

        self.assertEqual(tile.hostile_count, 1)

    def test_should_keep_a_partner_in_a_neutral_corporation_neutral(self):
        self.esi_affiliations.return_value = {OUTSIDER: (4001, None)}

        account = self.account()

        self.assertEqual(account.hostile, set())
        self.assertEqual({node["id"]: node["group"] for node in account.graph()["nodes"]}[4001], "corporation")
