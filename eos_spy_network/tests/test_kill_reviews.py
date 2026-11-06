"""The note and the cleared tick of a blue kill, and the settings tab listing every stored one."""

from aa_contacts.models import AllianceContact
from killtracker.models import EveKillmail

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from eos_spy_network import api, markers, snapshot
from eos_spy_network.models import KILL_NOTE_LENGTH, BlueKill, SpyConfiguration

from .base import ALLIANCE_ID, OTHER_ALLIANCE_ID, configure, make_user
from .test_kills import ALT, BLUE_ALLIANCE, VIEW_SUSPECTS, KillTestCase, add_killmail

MANAGE_SETTINGS = "eos_spy_network.manage_settings"


class ReviewTestCase(KillTestCase):
    """Two killmails of the alt, stored in the snapshot."""

    def setUp(self):
        super().setUp()
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID, days_ago=2)
        add_killmail(2, [ALT], victim_id=90000002, alliance_id=BLUE_ALLIANCE, days_ago=1)
        snapshot.update()

    @staticmethod
    def review(killmail_id, cleared=True, note=""):
        BlueKill.objects.filter(killmail_id=killmail_id).update(cleared=cleared, note=note)

    def report_marker(self):
        report = snapshot.Report(snapshot.current(), (), snapshot.kill_reviews(ALLIANCE_ID))
        suspect = next((suspect for suspect in report.tile(2001).suspects if suspect.user_id == self.user.pk), None)
        return suspect.markers.get(markers.BLUE_KILLS) if suspect else None


class TestReviewedReport(ReviewTestCase):
    def test_should_count_only_the_kills_not_cleared(self):
        self.review(1)

        marker = self.report_marker()

        self.assertEqual(marker.count, 1)
        self.assertEqual(marker.details, {"Name 90000002"})

    def test_should_keep_a_cleared_kill_in_the_rows(self):
        self.review(1, note="Fleet fight, agreed")

        rows = {row["killmail_id"]: row for row in self.report_marker().rows}

        self.assertTrue(rows[1]["cleared"])
        self.assertEqual(rows[1]["note"], "Fleet fight, agreed")
        self.assertFalse(rows[2]["cleared"])

    def test_should_drop_the_marker_once_every_kill_is_cleared(self):
        self.review(1)
        self.review(2)

        self.assertIsNone(self.report_marker())

    def test_should_still_count_a_kill_with_a_note_only(self):
        self.review(1, cleared=False, note="Asked him")

        self.assertEqual(self.report_marker().count, 2)

    def test_should_keep_the_review_through_a_recalculation(self):
        self.review(1, note="Agreed")

        snapshot.update()

        kill = BlueKill.objects.get(killmail_id=1)
        self.assertTrue(kill.cleared)
        self.assertEqual(kill.note, "Agreed")

    def test_should_keep_a_kill_whose_victim_is_no_longer_blue(self):
        # the row is a snapshot of the time it was found
        AllianceContact.objects.filter(contact_id=BLUE_ALLIANCE).delete()

        snapshot.update()

        kill = BlueKill.objects.get(killmail_id=2)
        self.assertEqual(kill.standing, 10)
        self.assertEqual(self.report_marker().count, 2)


class TestReviewedApi(ReviewTestCase):
    def test_should_leave_out_a_character_whose_kills_are_all_cleared(self):
        self.review(1)
        self.review(2)

        self.assertNotIn(ALT, api.character_markers())

    def test_should_keep_a_character_with_a_kill_not_cleared(self):
        self.review(1)

        self.assertEqual(api.character_markers()[ALT], [markers.BLUE_KILLS])

    def test_should_read_the_reviews_in_one_more_query(self):
        with CaptureQueriesContext(connection) as queries:
            api.character_markers()

        self.assertEqual(len(queries), 3)


class TestKillNote(ReviewTestCase):
    def setUp(self):
        super().setUp()
        self.viewer = make_user("viewer", VIEW_SUSPECTS)
        self.client.force_login(self.viewer)

    def post(self, killmail_id=1, character_id=ALT, **fields):
        return self.client.post(
            reverse("eos_spy_network:kill_note"),
            {"killmail_id": killmail_id, "character_id": character_id, **fields},
        )

    def test_should_store_the_note_and_the_tick(self):
        response = self.post(note="  Fleet   fight ", cleared="1")

        self.assertEqual(response.json(), {"note": "Fleet fight", "cleared": True})
        kill = BlueKill.objects.get(killmail_id=1)
        self.assertTrue(kill.cleared)
        self.assertEqual(kill.reviewed_by, self.viewer)
        self.assertIsNotNone(kill.reviewed_at)

    def test_should_untick_without_the_field(self):
        self.review(1, note="Agreed")

        self.post(note="Agreed")

        self.assertFalse(BlueKill.objects.get(killmail_id=1).cleared)

    def test_should_refuse_to_clear_without_a_note(self):
        response = self.post(note="   ", cleared="1")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(BlueKill.objects.get(killmail_id=1).cleared)

    def test_should_take_a_note_without_the_tick(self):
        response = self.post(note="Asked him")

        self.assertEqual(response.json(), {"note": "Asked him", "cleared": False})

    def test_should_refuse_a_note_too_long(self):
        response = self.post(note="x" * (KILL_NOTE_LENGTH + 1))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(BlueKill.objects.get(killmail_id=1).note, "")

    def test_should_not_find_the_kill_of_another_alliance(self):
        BlueKill.objects.filter(killmail_id=1).update(alliance_id=OTHER_ALLIANCE_ID)

        self.assertEqual(self.post(note="Agreed", cleared="1").status_code, 404)

    def test_should_need_view_suspects(self):
        self.client.force_login(make_user("settings", MANAGE_SETTINGS))

        response = self.post(note="Agreed", cleared="1")

        self.assertEqual(response.status_code, 302)
        self.assertFalse(BlueKill.objects.get(killmail_id=1).cleared)

    def test_should_show_a_cleared_kill_greyed_on_the_corporation_page(self):
        self.post(note="Fleet fight", cleared="1")

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, 'class="opacity-50"', count=1)
        self.assertContains(response, "Fleet fight")
        self.assertContains(response, 'data-eos-spy-network-kill-reload')

    def test_should_show_no_marker_once_every_kill_is_cleared(self):
        self.post(note="Agreed", cleared="1")
        self.post(killmail_id=2, note="Agreed", cleared="1")

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, "No markers.")


class TestSettingsTab(ReviewTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

    def get(self):
        return self.client.get(reverse("eos_spy_network:settings") + "?tab=kills")

    def test_should_list_every_kill_of_the_alliance_also_outside_the_time_frame(self):
        BlueKill.objects.filter(killmail_id=1).update(time=BlueKill.objects.get(killmail_id=1).time.replace(year=2020))
        configure(lookback_days=30)

        response = self.get()

        self.assertContains(response, "https://zkillboard.com/kill/1/")
        self.assertContains(response, "https://zkillboard.com/kill/2/")
        self.assertContains(response, 'id="eos-spy-network-settings-kills"')

    def test_should_leave_out_the_kills_of_another_alliance(self):
        BlueKill.objects.filter(killmail_id=1).update(alliance_id=OTHER_ALLIANCE_ID)

        response = self.get()

        self.assertNotContains(response, "https://zkillboard.com/kill/1/")

    def test_should_name_the_character_and_who_changed_the_review(self):
        self.client.post(reverse("eos_spy_network:kill_note"), {"killmail_id": 1, "character_id": ALT, "note": "Agreed", "cleared": "1"})

        response = self.get()

        self.assertContains(response, f"Char {ALT}")
        self.assertContains(response, "Last changed by admin main")

    def test_should_open_the_tab_asked_for(self):
        response = self.get()

        self.assertEqual(response.context["tab"], "kills")

    def test_should_show_the_note_without_a_button_to_a_viewer_without_view_suspects(self):
        self.review(1, cleared=False, note="Read only")
        self.client.force_login(make_user("settings", MANAGE_SETTINGS))

        response = self.get()

        self.assertContains(response, "Read only")
        self.assertNotContains(response, 'data-bs-target="#eos-spy-network-kill-note"')

    def test_should_say_so_without_a_kill(self):
        BlueKill.objects.all().delete()
        EveKillmail.objects.all().delete()

        self.assertContains(self.get(), "No blue kill stored.")

    def test_should_be_empty_without_an_alliance(self):
        config = SpyConfiguration.get_solo()
        config.alliance = None
        config.save()

        self.assertEqual(self.get().context["kills"], [])
