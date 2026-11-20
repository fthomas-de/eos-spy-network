from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from esi.exceptions import ESIErrorLimitException
from eve_sde.models import ItemCategory, ItemGroup, ItemType, NPCStation, Region

from django.utils import timezone

from eos_spy_network import capital_sweep, tasks
from eos_spy_network.models import CapitalContract

from .base import SpyTestCase, configure, make_corporation

ALLIANCE_CORP = 2001
FOREIGN_CORP = 2999
DERELIK = 10000001
FORGE = 10000002
NAGLFAR = 19722
STATION = 60000001
STRUCTURE = 1_000_000_000_001


def public(contract_id, corporation_id=ALLIANCE_CORP, kind="item_exchange", days=3, location=STATION):
    now = timezone.now()
    return SimpleNamespace(
        contract_id=contract_id, issuer_id=9001, issuer_corporation_id=corporation_id, type=kind,
        title="Dread", price=5e9, buyout=None, date_issued=now - timedelta(days=1),
        date_expired=now + timedelta(days=days), start_location_id=location,
    )


def item(type_id=NAGLFAR, quantity=1, included=True):
    return SimpleNamespace(type_id=type_id, quantity=quantity, is_included=included)


class TestSweep(SpyTestCase):
    def setUp(self):
        super().setUp()
        configure()
        make_corporation(ALLIANCE_CORP)
        make_corporation(FOREIGN_CORP, alliance_id=None)
        Region.objects.create(id=DERELIK, name="Derelik")
        Region.objects.create(id=FORGE, name="The Forge")
        # wormhole space is never asked
        Region.objects.create(id=11000001, name="A-R00001")
        NPCStation.objects.create(id=STATION, name="Station One")
        ItemCategory.objects.create(id=6, name="Ship", published=True)
        group = ItemGroup.objects.create(id=485, name="Dreadnought", category_id=6, published=True)
        ItemType.objects.create(id=NAGLFAR, name="Naglfar", group=group)
        self.listed = {DERELIK: [public(1)], FORGE: []}
        self.items = {1: [item()]}
        self.asked_regions = []
        self.asked_items = []
        self.timeouts = {}  # region ID -> how many times it fails before it answers

        def regions(region_id):
            self.asked_regions.append(region_id)
            if self.timeouts.get(region_id):
                self.timeouts[region_id] -= 1
                raise RuntimeError("timeout")
            answer = self.listed[region_id]
            if isinstance(answer, Exception):
                raise answer
            return answer

        def items(contract_id):
            self.asked_items.append(contract_id)
            answer = self.items[contract_id]
            if isinstance(answer, Exception):
                raise answer
            return answer

        for target, side_effect in (("_region_contracts", regions), ("_contract_items", items)):
            patcher = patch.object(capital_sweep, target, side_effect=side_effect)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_should_store_a_contract_of_an_alliance_corporation_with_its_items_and_place(self):
        self.assertEqual(capital_sweep.sweep(), 1)

        stored = CapitalContract.objects.get()
        self.assertEqual((stored.contract_id, stored.issuer_id, stored.location), (1, 9001, "Derelik, Station One"))
        self.assertEqual([(i.type_id, i.quantity, i.is_included) for i in stored.items.all()], [(NAGLFAR, 1, True)])

    def test_should_ask_known_space_only(self):
        capital_sweep.sweep()

        self.assertEqual(sorted(self.asked_regions), [DERELIK, FORGE])

    def test_should_leave_out_what_the_marker_never_shows(self):
        self.listed[FORGE] = [
            public(2, corporation_id=FOREIGN_CORP), public(3, kind="courier"), public(4, days=-1)
        ]
        self.items.update({2: [item()], 3: [item()], 4: [item()]})

        capital_sweep.sweep()

        self.assertEqual(list(CapitalContract.objects.values_list("pk", flat=True)), [1])
        self.assertEqual(self.asked_items, [1])

    def test_should_show_a_structure_by_its_id(self):
        self.listed[DERELIK] = [public(1, location=STRUCTURE)]

        capital_sweep.sweep()

        self.assertEqual(CapitalContract.objects.get().location, f"Derelik, structure {STRUCTURE}")

    def test_should_fetch_the_items_of_a_contract_once(self):
        capital_sweep.sweep()
        self.assertEqual(capital_sweep.sweep(), 0)

        self.assertEqual(self.asked_items, [1])

    def test_should_forget_a_contract_that_is_no_longer_listed(self):
        capital_sweep.sweep()
        self.listed[DERELIK] = []

        capital_sweep.sweep()

        self.assertFalse(CapitalContract.objects.exists())

    def test_should_keep_a_contract_while_a_region_failed(self):
        capital_sweep.sweep()
        self.listed[DERELIK] = []
        self.listed[FORGE] = RuntimeError("ESI down")

        capital_sweep.sweep()

        self.assertTrue(CapitalContract.objects.exists())

    def test_should_drop_an_expired_contract_even_when_a_region_failed(self):
        capital_sweep.sweep()
        CapitalContract.objects.update(date_expired=timezone.now() - timedelta(minutes=1))
        self.listed[FORGE] = RuntimeError("ESI down")

        capital_sweep.sweep()

        self.assertFalse(CapitalContract.objects.exists())

    def test_should_store_a_contract_whose_items_failed_at_the_next_sweep(self):
        self.items[1] = RuntimeError("ESI down")
        self.assertEqual(capital_sweep.sweep(), 0)
        self.assertFalse(CapitalContract.objects.exists())

        self.items[1] = [item()]

        self.assertEqual(capital_sweep.sweep(), 1)

    def test_should_ask_nothing_without_an_alliance(self):
        configure(alliance_id=None)

        self.assertEqual(capital_sweep.sweep(), 0)
        self.assertEqual(self.asked_regions, [])

    def test_should_ask_a_failed_region_again_in_the_same_sweep(self):
        capital_sweep.sweep()
        self.listed[DERELIK] = []
        self.listed[FORGE] = [public(2)]
        self.items[2] = [item()]
        self.timeouts[FORGE] = 1

        capital_sweep.sweep()

        # the second answer counts in full: the new contract is stored, the gone one forgotten
        self.assertEqual(list(CapitalContract.objects.values_list("pk", flat=True)), [2])

    def test_should_ask_a_failed_region_twice_at_most(self):
        self.timeouts[FORGE] = 5

        capital_sweep.sweep()

        self.assertEqual(self.asked_regions.count(FORGE), 2)

    def test_should_stop_at_the_error_limit_of_a_region(self):
        self.listed[DERELIK] = ESIErrorLimitException(reset=30)

        with self.assertRaises(ESIErrorLimitException):
            capital_sweep.sweep()

    def test_should_stop_at_the_error_limit_of_the_items(self):
        self.items[1] = ESIErrorLimitException(reset=30)

        with self.assertRaises(ESIErrorLimitException):
            capital_sweep.sweep()


class TestEsiCalls(SpyTestCase):
    def test_should_ask_esi_without_etag_and_cache(self):
        with patch.object(capital_sweep, "esi") as esi:
            capital_sweep._region_contracts(FORGE)
            capital_sweep._contract_items(1)

        contracts = esi.client.Contracts
        for operation in (contracts.GetContractsPublicRegionId, contracts.GetContractsPublicItemsContractId):
            operation.return_value.results.assert_called_once_with(use_etag=False, store_cache=False)


class TestSweepTask(SpyTestCase):
    def test_should_retry_after_the_error_limit_resets(self):
        with (
            patch.object(capital_sweep, "sweep", side_effect=ESIErrorLimitException(reset=30)),
            patch.object(tasks.sweep_capital_contracts, "retry") as retry,
        ):
            tasks.sweep_capital_contracts()

        retry.assert_called_once_with(countdown=30)
