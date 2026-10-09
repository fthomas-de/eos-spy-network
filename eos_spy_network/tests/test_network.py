from corptools.models import CharacterAudit, CharacterWalletJournalEntry, EveName

from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership

from eos_spy_network import snapshot
from eos_spy_network.network import connections

from .base import ALLIANCE_ID, SpyTestCase, configure, make_character, make_corporation, make_user

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
            {node["id"]: node["group"] for node in graph["nodes"]},
            {self.main.character_id: "main", 5001: "alt", OUTSIDER: "shared"},
        )
        self.assertEqual(len(graph["edges"]), 2)

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
