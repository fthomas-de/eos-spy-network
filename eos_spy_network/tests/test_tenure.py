"""Whether a character was in the Alliance when something happened (user, 2026-11-23)."""

from datetime import timedelta

from corptools.models import CharacterAudit, CorporationHistory, EveName

from django.utils import timezone

from eos_spy_network import markers, tenure
from eos_spy_network.models import CorporationAlliances
from eos_spy_network.tenure import Tenure

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
