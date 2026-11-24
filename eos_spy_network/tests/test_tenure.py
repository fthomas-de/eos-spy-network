"""Whether a character was in the Alliance when something happened (user, 2026-11-23)."""

from datetime import timedelta
from unittest.mock import patch

from corptools.models import CharacterAudit, CorporationHistory, EveName

from django.utils import timezone

from eos_spy_network import markers, tenure
from eos_spy_network.affiliations import Entity
from eos_spy_network.models import CharacterCorporations, CorporationAlliances
from eos_spy_network.tenure import Tenure, _esi_alliance_history as real_alliance_history
from eos_spy_network.tenure import _esi_corporation_history as real_corporation_history

from .base import ALLIANCE_ID, OTHER_ALLIANCE_ID, SpyTestCase, configure, make_corporation, make_user

NOW = timezone.now()
CHARACTER = 1
OUTSIDE_CORPORATION = 4000
INSIDE_CORPORATION = 2001


def ago(days):
    return NOW - timedelta(days=days)


class TestCounts(SpyTestCase):
    """The character is in a Corporation outside the Alliance until 50 days ago, then in 2001."""

    def tenure(self, alliances, corporations_now=()):
        characters = {CHARACTER: [(ago(100), OUTSIDE_CORPORATION), (ago(50), INSIDE_CORPORATION)]}
        return Tenure(ALLIANCE_ID, set(corporations_now), characters, alliances)

    def test_should_not_count_the_time_in_a_corporation_outside_the_alliance(self):
        found = self.tenure({OUTSIDE_CORPORATION: [], INSIDE_CORPORATION: [(ago(400), ALLIANCE_ID)]})

        self.assertFalse(found.counts(CHARACTER, ago(60)))
        self.assertTrue(found.counts(CHARACTER, ago(10)))

    def test_should_not_count_the_time_before_the_corporation_joined_the_alliance(self):
        # the character was in 2001 for 50 days, the Corporation joined the Alliance 30 days ago
        found = self.tenure({INSIDE_CORPORATION: [(ago(400), None), (ago(30), ALLIANCE_ID)]})

        self.assertFalse(found.counts(CHARACTER, ago(40)))
        self.assertTrue(found.counts(CHARACTER, ago(10)))

    def test_should_not_count_the_time_after_the_corporation_left_the_alliance(self):
        found = self.tenure({INSIDE_CORPORATION: [(ago(400), ALLIANCE_ID), (ago(20), None)]})

        self.assertTrue(found.counts(CHARACTER, ago(30)))
        self.assertFalse(found.counts(CHARACTER, ago(10)))

    def test_should_not_count_a_corporation_in_another_alliance(self):
        found = self.tenure({INSIDE_CORPORATION: [(ago(400), OTHER_ALLIANCE_ID)]})

        self.assertFalse(found.counts(CHARACTER, ago(10)))

    def test_should_fall_back_to_the_alliance_of_today_without_a_history(self):
        self.assertTrue(self.tenure({}, {INSIDE_CORPORATION}).counts(CHARACTER, ago(10)))
        self.assertFalse(self.tenure({}, set()).counts(CHARACTER, ago(10)))

    def test_should_count_an_undated_item_and_refuse_an_unknown_character_or_a_date_before_the_first_record(self):
        found = self.tenure({INSIDE_CORPORATION: [(ago(400), ALLIANCE_ID)]})

        self.assertTrue(found.counts(CHARACTER, None))
        self.assertFalse(found.counts(999, ago(10)))
        self.assertFalse(found.counts(CHARACTER, ago(200)))


class TestLoad(SpyTestCase):
    def setUp(self):
        super().setUp()
        self.config = configure()
        make_corporation(INSIDE_CORPORATION)
        self.user = make_user("member")
        self.main = self.user.profile.main_character
        self.audit = CharacterAudit.objects.create(character=self.main)

    def load(self, since=None):
        return tenure.load(self.config, markers.roster(self.config).characters, since)

    def join(self, corporation_id, days_ago, record_id):
        name, _created = EveName.objects.get_or_create(
            eve_id=corporation_id, defaults={"name": f"Corp {corporation_id}", "category": "corporation"}
        )
        CorporationHistory.objects.create(
            character=self.audit, corporation_id=corporation_id, corporation_name=name, record_id=record_id,
            start_date=ago(days_ago),
        )

    def store(self, corporation_id, history, fetched_days_ago=0):
        CorporationAlliances.objects.create(
            corporation_id=corporation_id, history=history, fetched_at=ago(fetched_days_ago)
        )

    def test_should_read_the_corporations_of_corptools_and_their_alliance_histories(self):
        self.join(OUTSIDE_CORPORATION, 100, 1)
        self.join(INSIDE_CORPORATION, 50, 2)
        self.store(OUTSIDE_CORPORATION, [])
        self.store(INSIDE_CORPORATION, [[ago(400).isoformat(), ALLIANCE_ID]])

        found = self.load()

        self.assertFalse(found.counts(self.main.character_id, ago(60)))
        self.assertTrue(found.counts(self.main.character_id, ago(10)))
        self.esi_alliance_history.assert_not_called()

    def test_should_take_the_corporation_of_today_for_a_character_corptools_has_no_history_of(self):
        found = self.load()

        # no ESI answer either: Auth has 2001 in the Alliance, from the beginning
        self.assertTrue(found.counts(self.main.character_id, ago(3000)))

    def test_should_ask_esi_for_a_missing_history_and_keep_it(self):
        self.join(INSIDE_CORPORATION, 50, 1)
        self.esi_alliance_history.return_value = [[ago(400).isoformat(), ALLIANCE_ID], [ago(20).isoformat(), None]]

        found = self.load()

        self.esi_alliance_history.assert_called_once_with(INSIDE_CORPORATION)
        self.assertEqual(CorporationAlliances.objects.get(pk=INSIDE_CORPORATION).history[1][1], None)
        self.assertTrue(found.counts(self.main.character_id, ago(30)))
        self.assertFalse(found.counts(self.main.character_id, ago(10)))

    def test_should_not_ask_again_within_a_day_but_after_it(self):
        self.join(INSIDE_CORPORATION, 50, 1)
        self.store(INSIDE_CORPORATION, [[ago(400).isoformat(), ALLIANCE_ID]], fetched_days_ago=0)

        self.load()
        self.esi_alliance_history.assert_not_called()

        CorporationAlliances.objects.update(fetched_at=ago(2))
        self.esi_alliance_history.return_value = [[ago(400).isoformat(), OTHER_ALLIANCE_ID]]
        found = self.load()

        self.esi_alliance_history.assert_called_once_with(INSIDE_CORPORATION)
        self.assertFalse(found.counts(self.main.character_id, ago(10)))

    def test_should_keep_the_stored_history_when_esi_cannot_be_asked(self):
        self.join(INSIDE_CORPORATION, 50, 1)
        self.store(INSIDE_CORPORATION, [[ago(400).isoformat(), ALLIANCE_ID]], fetched_days_ago=5)

        found = self.load()

        self.esi_alliance_history.assert_called_once_with(INSIDE_CORPORATION)
        self.assertTrue(found.counts(self.main.character_id, ago(10)))

    def test_should_not_ask_for_npc_corporations_or_ones_the_time_frame_never_reaches(self):
        self.join(OUTSIDE_CORPORATION, 300, 1)
        self.join(INSIDE_CORPORATION, 50, 2)
        self.join(1000125, 20, 3)
        self.esi_alliance_history.return_value = []

        # the first Corporation ended 50 days ago, before the 30 day time frame; the last is an NPC Corporation
        self.load(since=ago(30))

        self.esi_alliance_history.assert_called_once_with(INSIDE_CORPORATION)

    def test_should_stop_asking_after_five_failures_in_a_row(self):
        for number, corporation_id in enumerate(range(4000, 4008), start=1):
            self.join(corporation_id, 300 - number * 10, number)

        self.load()

        self.assertEqual(self.esi_alliance_history.call_count, tenure.MAX_FAILURES)

    def test_should_trust_a_history_that_has_stood_for_long_for_up_to_a_week(self):
        self.join(OUTSIDE_CORPORATION, 100, 1)
        self.store(OUTSIDE_CORPORATION, [[ago(400).isoformat(), OTHER_ALLIANCE_ID]], fetched_days_ago=5)

        self.load()
        self.esi_alliance_history.assert_not_called()

        CorporationAlliances.objects.update(fetched_at=ago(8))
        self.load()
        self.esi_alliance_history.assert_called_once_with(OUTSIDE_CORPORATION)

    def test_should_ask_daily_for_a_history_that_changed_lately(self):
        self.join(OUTSIDE_CORPORATION, 100, 1)
        # the last change was 8 days before the fetch: a thirtieth of that is under a day
        self.store(OUTSIDE_CORPORATION, [[ago(10).isoformat(), OTHER_ALLIANCE_ID]], fetched_days_ago=2)

        self.load()

        self.esi_alliance_history.assert_called_once_with(OUTSIDE_CORPORATION)

    def test_should_ask_daily_for_a_corporation_that_may_just_have_left_our_alliance(self):
        self.join(OUTSIDE_CORPORATION, 100, 1)
        # Auth no longer has it in the Alliance, the stored history still does
        self.store(OUTSIDE_CORPORATION, [[ago(400).isoformat(), ALLIANCE_ID]], fetched_days_ago=3)

        self.load()

        self.esi_alliance_history.assert_called_once_with(OUTSIDE_CORPORATION)

    def test_should_ask_daily_for_a_corporation_auth_has_in_the_alliance(self):
        self.join(INSIDE_CORPORATION, 50, 1)
        # a Corporation that joined: the stored history, long stable, does not know yet
        self.store(INSIDE_CORPORATION, [[ago(400).isoformat(), OTHER_ALLIANCE_ID]], fetched_days_ago=3)

        self.load()

        self.esi_alliance_history.assert_called_once_with(INSIDE_CORPORATION)

    def test_should_remember_that_esi_knows_nothing_of_a_corporation(self):
        for number, corporation_id in enumerate(range(4000, 4008), start=1):
            self.join(corporation_id, 300 - number * 10, number)
        # ESI's 404 is an answer: eight of them are no outage, and none is asked again
        self.esi_alliance_history.return_value = []

        self.load()
        self.load()

        self.assertEqual(self.esi_alliance_history.call_count, 8)
        self.assertEqual(CorporationAlliances.objects.filter(history=[]).count(), 8)


class NotFound(Exception):
    status_code = 404


class TestEsiAnswers(SpyTestCase):
    def ask(self, ask, operation, error):
        with patch("eos_spy_network.tenure.esi") as provider:
            call = getattr(getattr(provider.client, operation[0]), operation[1])
            call.return_value.results.side_effect = error
            return ask(1)

    def test_should_take_a_404_for_an_empty_history_and_any_other_error_for_no_answer(self):
        for ask, operation in (
            (real_alliance_history, ("Corporation", "GetCorporationsCorporationIdAlliancehistory")),
            (real_corporation_history, ("Character", "GetCharactersCharacterIdCorporationhistory")),
        ):
            self.assertEqual(self.ask(ask, operation, NotFound()), [])
            self.assertIsNone(self.ask(ask, operation, OSError("ESI down")))


class TestWasOurs(SpyTestCase):
    """A counterpart that was in 2001 until 20 days ago; 2001 has been in the Alliance for years (user, 2026-11-24)."""

    def setUp(self):
        super().setUp()
        self.found = Tenure(
            ALLIANCE_ID,
            {INSIDE_CORPORATION},
            {CHARACTER: [(ago(100), INSIDE_CORPORATION), (ago(20), OUTSIDE_CORPORATION)]},
            {INSIDE_CORPORATION: [(ago(400), ALLIANCE_ID)], OUTSIDE_CORPORATION: [(ago(400), OTHER_ALLIANCE_ID)]},
        )

    def test_should_answer_for_a_character_by_its_corporation_at_the_time(self):
        self.assertTrue(self.found.was_ours(CHARACTER, ago(30)))
        self.assertFalse(self.found.was_ours(CHARACTER, ago(10)))
        # undated: today
        self.assertFalse(self.found.was_ours(CHARACTER, None))

    def test_should_answer_for_a_corporation_and_the_alliance_itself(self):
        self.assertTrue(self.found.was_ours(INSIDE_CORPORATION, ago(10)))
        self.assertFalse(self.found.was_ours(OUTSIDE_CORPORATION, ago(10)))
        self.assertTrue(self.found.was_ours(ALLIANCE_ID, ago(10)))
        self.assertFalse(self.found.was_ours(OTHER_ALLIANCE_ID, ago(10)))

    def test_should_take_an_unknown_id_for_an_outsider(self):
        self.assertFalse(self.found.was_ours(999, ago(10)))


class TestPrepare(SpyTestCase):
    COUNTERPART = 90000200

    def setUp(self):
        super().setUp()
        self.config = configure()
        make_corporation(INSIDE_CORPORATION)
        make_user("member")
        self.tenure = tenure.load(self.config, markers.roster(self.config).characters)

    def prepare(self, corporation_id=OUTSIDE_CORPORATION, alliance_id=None):
        entity = Entity(self.COUNTERPART, "Counterpart", "character", corporation_id, alliance_id)
        self.tenure.prepare({self.COUNTERPART}, {self.COUNTERPART: entity})

    def test_should_read_the_corporations_of_corptools_for_a_counterpart_with_an_audit(self):
        from allianceauth.eveonline.models import EveCharacter

        character = EveCharacter.objects.create(
            character_id=self.COUNTERPART, character_name="Counterpart", corporation_id=OUTSIDE_CORPORATION,
            corporation_name="Out", corporation_ticker="OUT",
        )
        audit = CharacterAudit.objects.create(character=character)
        name = EveName.objects.create(eve_id=INSIDE_CORPORATION, name="In", category="corporation")
        CorporationHistory.objects.create(
            character=audit, corporation_id=INSIDE_CORPORATION, corporation_name=name, record_id=1, start_date=ago(100)
        )

        self.prepare()

        self.esi_corporation_history.assert_not_called()
        self.assertTrue(self.tenure.was_ours(self.COUNTERPART, ago(10)))

    def test_should_ask_esi_for_the_others_and_keep_the_answer(self):
        self.esi_corporation_history.return_value = [
            [ago(100).isoformat(), INSIDE_CORPORATION], [ago(20).isoformat(), OUTSIDE_CORPORATION]
        ]

        self.prepare()

        self.esi_corporation_history.assert_called_once_with(self.COUNTERPART)
        self.assertEqual(CharacterCorporations.objects.get(pk=self.COUNTERPART).history[1][1], OUTSIDE_CORPORATION)
        self.assertTrue(self.tenure.was_ours(self.COUNTERPART, ago(30)))
        self.assertFalse(self.tenure.was_ours(self.COUNTERPART, ago(10)))

    def test_should_take_todays_corporation_and_alliance_when_esi_cannot_be_asked(self):
        # ESI puts it into a Corporation Auth does not know, in our Alliance: today stands in
        self.prepare(corporation_id=4001, alliance_id=ALLIANCE_ID)

        self.assertTrue(self.tenure.was_ours(self.COUNTERPART, ago(300)))

    def test_should_look_up_a_counterpart_once_per_run(self):
        corporation = Entity(4002, "Corp", "corporation")

        # ESI cannot answer: the second call must not ask again
        self.esi_alliance_history.reset_mock()
        self.tenure.prepare({4002}, {4002: corporation})
        self.tenure.prepare({4002}, {4002: corporation})

        self.esi_alliance_history.assert_called_once_with(4002)

    def store(self, corporation_id, fetched_days_ago):
        CharacterCorporations.objects.create(
            character_id=self.COUNTERPART,
            history=[[ago(400).isoformat(), corporation_id]],
            fetched_at=ago(fetched_days_ago),
        )

    def test_should_trust_a_counterpart_history_that_has_stood_for_long(self):
        self.store(OUTSIDE_CORPORATION, fetched_days_ago=3)

        self.prepare()

        self.esi_corporation_history.assert_not_called()

    def test_should_ask_daily_for_a_counterpart_in_one_of_our_corporations(self):
        # the day it leaves is the one that matters
        self.store(INSIDE_CORPORATION, fetched_days_ago=3)

        self.prepare()

        self.esi_corporation_history.assert_called_once_with(self.COUNTERPART)
