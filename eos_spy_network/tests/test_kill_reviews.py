"""The note and the cleared tick of a blue kill, and the settings tab listing every stored one."""

from aa_contacts.models import AllianceContact
from killtracker.models import EveKillmail

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from allianceauth.authentication.models import CharacterOwnership

from eos_spy_network import api, markers, snapshot
from eos_spy_network.models import KILL_NOTE_LENGTH, BlueKill, ReviewLog, SpyConfiguration

from .base import ALLIANCE_ID, OTHER_ALLIANCE_ID, configure, make_character, make_user
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

    def test_should_clear_without_a_note_for_an_admin(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

        response = self.post(note="", cleared="1")

        self.assertEqual(response.json(), {"note": "", "cleared": True})
        self.assertTrue(BlueKill.objects.get(killmail_id=1).cleared)

    def test_should_ask_an_admin_for_a_note_on_the_corporation_page(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, 'id="eos-spy-network-kill-note"')
        self.assertNotContains(response, "data-eos-spy-network-kill-admin")

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


class TestClearedList(ReviewTestCase):
    """The mains whose every finding is cleared, at the foot of the Corporation page."""

    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

    def cleared(self, disabled=()):
        report = snapshot.Report(snapshot.current(), disabled, snapshot.kill_reviews(ALLIANCE_ID))
        return report.tile(2001).cleared

    def get(self):
        return self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

    def test_should_list_a_main_once_every_kill_is_cleared(self):
        self.review(1, note="Bomb")
        self.review(2, note="Fleet fight")

        (cleared,) = self.cleared()

        self.assertEqual(cleared["main"].character_id, self.main.character_id)
        self.assertEqual({row["note"] for row in cleared["rows"]}, {"Bomb", "Fleet fight"})
        self.assertEqual({row["killmail_id"] for row in cleared["rows"]}, {1, 2})

    def test_should_leave_out_a_main_with_a_kill_still_open(self):
        self.review(1, note="Bomb")

        self.assertEqual(self.cleared(), [])

    def test_should_leave_out_a_main_whose_marker_is_switched_off(self):
        self.review(1)
        self.review(2)

        self.assertEqual(self.cleared(disabled=(markers.BLUE_KILLS,)), [])

    def test_should_show_the_cleared_kills_on_the_corporation_page(self):
        self.review(1, note="Bomb")
        self.review(2, note="Fleet fight")

        response = self.get()

        self.assertContains(response, "Cleared findings")
        self.assertContains(response, "Fleet fight")
        self.assertContains(response, "https://zkillboard.com/kill/2/")
        self.assertContains(response, "data-eos-spy-network-cleared-search")

    def test_should_show_no_cleared_list_while_a_kill_is_open(self):
        self.review(1, note="Bomb")

        self.assertNotContains(self.get(), "Cleared findings")


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

    def test_should_leave_out_an_own_kill_copied_before(self):
        BlueKill.objects.filter(killmail_id=1).update(victim_id=self.main.character_id)

        response = self.get()

        self.assertNotContains(response, "https://zkillboard.com/kill/1/")
        self.assertContains(response, "https://zkillboard.com/kill/2/")

    def test_should_show_the_value_in_million(self):
        BlueKill.objects.filter(killmail_id=1).update(value=2_500_000.5)

        response = self.get()

        self.assertContains(response, "2.5 M")
        self.assertContains(response, 'data-order="2500000.500000"')

    def test_should_open_the_tab_asked_for(self):
        response = self.get()

        self.assertEqual(response.context["tab"], "kills")

    def test_should_let_the_admin_clear_without_a_note(self):
        self.assertContains(self.get(), "data-eos-spy-network-kill-admin")

    def test_should_leave_out_a_kill_below_the_minimum_value(self):
        BlueKill.objects.filter(killmail_id=1).update(value=10_000)
        configure(min_kill_value=1)

        response = self.get()

        self.assertNotContains(response, "https://zkillboard.com/kill/1/")
        # killmail 2 has no known value: it counts
        self.assertContains(response, "https://zkillboard.com/kill/2/")

    def test_should_leave_out_a_kill_of_an_ignored_ship(self):
        BlueKill.objects.filter(killmail_id=1).update(ship="Capsule")
        configure(ignored_ships=["Capsule"])

        response = self.get()

        self.assertNotContains(response, "https://zkillboard.com/kill/1/")
        self.assertContains(response, "https://zkillboard.com/kill/2/")

    def test_should_keep_the_findings_from_a_viewer_without_view_suspects(self):
        # manage_settings changes the settings; who is suspected is view_suspects' to see (user, 2026-11-12)
        self.review(1, cleared=False, note="Read only")
        self.client.force_login(make_user("settings", MANAGE_SETTINGS))

        response = self.get()

        self.assertNotContains(response, "Read only")
        self.assertNotContains(response, "eos-spy-network-settings-kills")
        self.assertNotContains(response, "eos-spy-network-settings-contacts")
        self.assertNotContains(response, "eos-spy-network-settings-log")
        self.assertContains(response, "eos-spy-network-settings-alliance")

    def test_should_say_so_without_a_kill(self):
        BlueKill.objects.all().delete()
        EveKillmail.objects.all().delete()

        self.assertContains(self.get(), "No blue kill stored.")

    def test_should_be_empty_without_an_alliance(self):
        config = SpyConfiguration.get_solo()
        config.alliance = None
        config.save()

        self.assertEqual(self.get().context["kills"], [])


class TestPerMainAndKillmail(ReviewTestCase):
    """Killmail 3: the main and its alt on it, and a second main of the same Corporation."""

    def setUp(self):
        super().setUp()
        self.other = make_user("other")
        self.other_main = self.other.profile.main_character.character_id
        add_killmail(3, [self.main.character_id, ALT, self.other_main], victim_id=90000003, alliance_id=ALLIANCE_ID)
        snapshot.update()
        self.viewer = make_user("viewer", VIEW_SUSPECTS, MANAGE_SETTINGS)
        self.client.force_login(self.viewer)

    def post(self, character_id=ALT, **fields):
        return self.client.post(
            reverse("eos_spy_network:kill_note"), {"killmail_id": 3, "character_id": character_id, **fields}
        )

    def test_should_show_one_row_per_killmail_with_the_mains_characters(self):
        rows = [row for row in self.report_marker().rows if row["killmail_id"] == 3]

        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]["character"].split(", ")), {self.main.character_name, f"Char {ALT}"})
        self.assertEqual(self.report_marker().count, 3)

    def test_should_clear_every_character_of_the_main_with_one_tick(self):
        self.post(note="Fleet fight", cleared="1")

        kills = BlueKill.objects.filter(killmail_id=3, character_id__in=[self.main.character_id, ALT])
        self.assertEqual([kill.cleared for kill in kills], [True, True])
        self.assertEqual(self.report_marker().count, 2)

    def test_should_leave_the_other_main_open(self):
        self.post(note="Fleet fight", cleared="1")

        self.assertFalse(BlueKill.objects.get(killmail_id=3, character_id=self.other_main).cleared)

    def test_should_keep_the_killmail_open_while_one_character_is_open(self):
        # a review of one row alone, from before the rows were grouped
        BlueKill.objects.filter(killmail_id=3, character_id=ALT).update(cleared=True, note="Old")

        row = next(row for row in self.report_marker().rows if row["killmail_id"] == 3)

        self.assertFalse(row["cleared"])
        self.assertEqual(row["note"], "Old")

    def test_should_list_one_row_per_main_and_killmail_in_the_settings_tab(self):
        response = self.client.get(reverse("eos_spy_network:settings") + "?tab=kills")

        self.assertEqual(len([kill for kill in response.context["kills"] if kill.killmail_id == 3]), 2)

    def test_should_show_the_tick_as_a_checkbox(self):
        self.post(note="Fleet fight", cleared="1")

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        # four kill rows and three day rows (the main's two days, the other main's one)
        self.assertContains(response, "data-eos-spy-network-kill-tick", count=7)
        self.assertContains(response, "checked", count=1)


class TestKillLinks(ReviewTestCase):
    """Killmail 3: the alt shot an alt of another account; killmails 1 and 2 hit victims without an account."""

    VICTIM_ALT = 5002

    def setUp(self):
        super().setUp()
        victim = make_user("victim")
        self.victim_main = victim.profile.main_character
        alt = make_character(self.VICTIM_ALT)
        CharacterOwnership.objects.create(user=victim, character=alt, owner_hash="hash-victim")
        add_killmail(3, [ALT], victim_id=self.VICTIM_ALT, corporation_id=2002, alliance_id=ALLIANCE_ID)
        snapshot.update()
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS, MANAGE_SETTINGS))

    def assert_links(self, response):
        self.assertContains(response, f'href="https://evewho.com/character/{ALT}"')
        self.assertContains(response, f'href="https://evewho.com/character/{self.VICTIM_ALT}"')
        self.assertContains(response, 'href="https://evewho.com/corporation/2002"')
        self.assertContains(response, f'href="https://evewho.com/alliance/{BLUE_ALLIANCE}"')
        # the victim's main, not the victim: the audit is per account
        audit_url = reverse("corptools:reactmain", args=[self.victim_main.character_id])
        self.assertContains(response, f'href="{audit_url}"')
        # killmails 1 and 2: victims without an account get none
        self.assertContains(response, 'title="Audit"', count=1)

    def test_should_link_the_kill_on_the_corporation_page(self):
        self.assert_links(self.client.get(reverse("eos_spy_network:corporation", args=[2001])))

    def test_should_link_the_kill_in_the_settings_tab(self):
        self.assert_links(self.client.get(reverse("eos_spy_network:settings") + "?tab=kills"))

    def test_should_show_no_victim_link_for_a_snapshot_without_victim_ids(self):
        current = snapshot.current()
        for corporation in current.data["corporations"]:
            for suspect in corporation["suspects"]:
                for marker in suspect["markers"]:
                    for row in marker.get("rows", []):
                        row.pop("victim_id", None)
        current.save()

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertNotContains(response, f'href="https://evewho.com/character/{self.VICTIM_ALT}"')
        self.assertNotContains(response, 'title="Audit"')
        self.assertNotContains(response, 'href="https://evewho.com/character/"')


class TestDayNote(ReviewTestCase):
    """Killmail 3 on the day of killmail 2: two kills of the main that day, killmail 1 the day before."""

    def setUp(self):
        super().setUp()
        add_killmail(3, [ALT], victim_id=90000003, alliance_id=ALLIANCE_ID, days_ago=1)
        snapshot.update()
        self.day = BlueKill.objects.get(killmail_id=2).time.date().isoformat()
        self.day_before = BlueKill.objects.get(killmail_id=1).time.date().isoformat()
        self.viewer = make_user("viewer", VIEW_SUSPECTS)
        self.client.force_login(self.viewer)

    def post(self, day=None, main_id=None, **fields):
        return self.client.post(
            reverse("eos_spy_network:kill_day_note"),
            {"main_id": main_id or self.main.character_id, "date": day or self.day, **fields},
        )

    def test_should_clear_every_open_kill_of_the_day(self):
        response = self.post(note="bomb", cleared="1")

        self.assertEqual(response.json(), {"note": "bomb", "cleared": True, "count": 2})
        self.assertEqual(
            dict(BlueKill.objects.values_list("killmail_id", "cleared")), {1: False, 2: True, 3: True}
        )
        self.assertEqual(self.report_marker().count, 1)

    def test_should_leave_a_cleared_kill_of_the_day_alone(self):
        self.review(2, note="Fleet fight")

        self.post(note="bomb", cleared="1")

        self.assertEqual(BlueKill.objects.get(killmail_id=2).note, "Fleet fight")
        self.assertEqual(BlueKill.objects.get(killmail_id=3).note, "bomb")

    def test_should_log_each_killmail(self):
        self.review(3, cleared=False, note="Asked him")

        self.post(note="bomb", cleared="1")

        logs = {log.key: log for log in ReviewLog.objects.all()}
        self.assertEqual(set(logs), {"2", "3"})
        self.assertEqual(logs["3"].previous_note, "Asked him")
        self.assertEqual(logs["3"].changed_by, self.viewer)

    def test_should_refuse_to_clear_without_a_note(self):
        self.assertEqual(self.post(note=" ", cleared="1").status_code, 400)
        self.assertFalse(BlueKill.objects.filter(cleared=True).exists())

    def test_should_refuse_a_malformed_date(self):
        self.assertEqual(self.post(day="13.11.2026", note="bomb").status_code, 400)

    def test_should_not_find_the_day_of_another_main(self):
        other = make_user("other").profile.main_character.character_id

        self.assertEqual(self.post(main_id=other, note="bomb", cleared="1").status_code, 404)
        self.assertFalse(BlueKill.objects.filter(cleared=True).exists())

    def test_should_not_find_a_day_without_open_kills(self):
        self.review(1, note="Agreed")

        self.assertEqual(self.post(day=self.day_before, note="bomb", cleared="1").status_code, 404)

    def test_should_need_view_suspects(self):
        self.client.force_login(make_user("settings", MANAGE_SETTINGS))

        self.assertEqual(self.post(note="bomb", cleared="1").status_code, 302)
        self.assertFalse(BlueKill.objects.filter(cleared=True).exists())

    def test_should_head_each_date_with_its_open_kills(self):
        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, f'data-eos-spy-network-kill-day="{self.day}"', count=1)
        self.assertContains(response, f'data-eos-spy-network-kill-day="{self.day_before}"', count=1)
        self.assertEqual([row["day_open"] for row in self.report_marker().rows], [2, 2, 1])

    def test_should_lock_a_day_whose_kills_are_all_cleared(self):
        self.review(1, note="Agreed")

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertNotContains(response, f'data-eos-spy-network-kill-day="{self.day_before}"')
        self.assertRegex(response.content.decode(), r"checked\s+disabled>")


class TestNotePresets(ReviewTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS)
        self.client.force_login(self.admin)

    def save(self, presets):
        return self.client.post(
            reverse("eos_spy_network:settings"),
            {
                "alliance": SpyConfiguration.get_solo().alliance.pk,
                "hostile_below": "0",
                "blue_from": "5",
                "min_kill_value": "0",
                "note_presets": presets,
                "corp_changes_per_year": "4",
                "lookback_days": "365",
            },
        )

    def test_should_start_with_bomb_and_sb_ratting(self):
        self.assertEqual(SpyConfiguration.get_solo().note_presets, ["bomb", "sb ratting"])

    def test_should_offer_a_button_per_text_in_the_popup(self):
        for page in (reverse("eos_spy_network:corporation", args=[2001]), reverse("eos_spy_network:settings")):
            response = self.client.get(page)

            self.assertContains(response, 'data-eos-spy-network-kill-preset="bomb"')
            self.assertContains(response, 'data-eos-spy-network-kill-preset="sb ratting"')

    def test_should_offer_no_buttons_without_a_text(self):
        configure(note_presets=[])

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertNotContains(response, "data-eos-spy-network-kill-presets")

    def test_should_save_free_text(self):
        response = self.save(["  Fleet   fight ", "bomb", "Fleet fight", " "])

        self.assertRedirects(response, reverse("eos_spy_network:settings"))
        self.assertEqual(SpyConfiguration.get_solo().note_presets, ["Fleet fight", "bomb"])

    def test_should_refuse_a_text_longer_than_a_note(self):
        response = self.save(["x" * (KILL_NOTE_LENGTH + 1)])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SpyConfiguration.get_solo().note_presets, ["bomb", "sb ratting"])

    def test_should_offer_the_stored_texts_as_free_text_in_the_settings(self):
        response = self.client.get(reverse("eos_spy_network:settings"))

        self.assertContains(response, "data-eos-spy-network-create")
        self.assertContains(response, '<option value="sb ratting" selected>sb ratting</option>', html=True)
