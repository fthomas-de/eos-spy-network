from unittest.mock import patch

from corptools.models import EveName

from allianceauth.eveonline.models import EveCorporationInfo

from eos_spy_network.affiliations import _esi_affiliations, _esi_names, resolve

from .base import OTHER_ALLIANCE_ID, SpyTestCase, make_character, make_corporation

STRANGER = 90000200
STRANGER_CORP = 98000300
STRANGER_ALLIANCE = 99000400
PROVIDER = "allianceauth.eveonline.providers.open_api_provider"


class TestKnownData(SpyTestCase):
    def test_should_take_a_character_auth_knows_without_asking_esi(self):
        make_character(STRANGER, corporation_id=4001, alliance_id=OTHER_ALLIANCE_ID)

        entities = resolve({STRANGER})

        self.assertEqual(entities[STRANGER].corporation_id, 4001)
        self.assertEqual(entities[STRANGER].alliance_id, OTHER_ALLIANCE_ID)
        self.assertEqual(entities[4001].name, "Corp 4001")
        self.assertEqual(entities[OTHER_ALLIANCE_ID].category, "alliance")
        self.esi_names.assert_not_called()
        self.esi_affiliations.assert_not_called()

    def test_should_take_the_alliance_of_a_corporation_auth_knows(self):
        make_corporation(4002, alliance_id=OTHER_ALLIANCE_ID)

        entities = resolve({4002})

        self.assertEqual(entities[4002].category, "corporation")
        self.assertEqual(entities[4002].alliance_id, OTHER_ALLIANCE_ID)
        self.esi_corporation_alliance.assert_not_called()


class TestEsi(SpyTestCase):
    def test_should_ask_esi_for_a_stranger_corptools_only_names(self):
        # corptools knows the name but not the Corporation: that is left to ESI
        EveName.objects.create(eve_id=STRANGER, name="Stranger", category="character")
        self.esi_affiliations.return_value = {STRANGER: (STRANGER_CORP, STRANGER_ALLIANCE)}
        self.esi_names.return_value = {STRANGER_CORP: ("Far Corp", "corporation"), STRANGER_ALLIANCE: ("Far Alliance", "alliance")}

        entities = resolve({STRANGER})

        self.esi_affiliations.assert_called_once_with([STRANGER])
        self.assertEqual(entities[STRANGER].name, "Stranger")
        self.assertEqual(entities[STRANGER].corporation_id, STRANGER_CORP)
        self.assertEqual(entities[STRANGER_CORP].name, "Far Corp")
        self.assertEqual(entities[STRANGER_CORP].alliance_id, STRANGER_ALLIANCE)
        self.assertEqual(entities[STRANGER_ALLIANCE].name, "Far Alliance")

    def test_should_name_the_corporation_from_auth_when_it_knows_it(self):
        EveName.objects.create(eve_id=STRANGER, name="Stranger", category="character")
        EveCorporationInfo.objects.create(
            corporation_id=STRANGER_CORP, corporation_name="Known Corp", corporation_ticker="KNOWN", member_count=1
        )
        self.esi_affiliations.return_value = {STRANGER: (STRANGER_CORP, None)}

        entities = resolve({STRANGER})

        self.assertEqual(entities[STRANGER_CORP].name, "Known Corp")
        self.assertIsNone(entities[STRANGER].alliance_id)

    def test_should_ask_esi_what_a_totally_unknown_id_is(self):
        self.esi_names.return_value = {STRANGER: ("Ghost", "character")}

        entities = resolve({STRANGER})

        self.assertEqual(entities[STRANGER].category, "character")
        self.esi_affiliations.assert_called_once_with([STRANGER])

    def test_should_fall_back_to_the_id_when_esi_knows_nothing(self):
        entities = resolve({STRANGER})

        self.assertEqual(entities[STRANGER].name, str(STRANGER))
        self.assertIsNone(entities[STRANGER].corporation_id)


class TestEsiFailure(SpyTestCase):
    def test_should_survive_a_failing_names_request(self):
        with patch(f"{PROVIDER}.post_names", side_effect=OSError("ESI down")):
            self.assertEqual(_esi_names([STRANGER]), {})

    def test_should_survive_a_failing_affiliation_request(self):
        with patch(f"{PROVIDER}.get_affiliations", side_effect=OSError("ESI down")):
            self.assertEqual(_esi_affiliations([STRANGER]), {})
