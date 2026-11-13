"""The note and the cleared tick of a friendly hostile contact: per main, contact and standing."""

from corptools.models import CharacterAudit, CharacterContact

from django.urls import reverse

from eos_spy_network import api, markers, snapshot
from eos_spy_network.models import FindingReview, ReviewLog

from .base import ALLIANCE_ID, OTHER_ALLIANCE_ID, configure, make_user
from .test_markers import HOSTILE_CORP, HOSTILE_MEMBER, MarkerTestCase, eve_name

VIEW_SUSPECTS = "eos_spy_network.view_suspects"
MANAGE_SETTINGS = "eos_spy_network.manage_settings"
ALT = 5001


class FindingTestCase(MarkerTestCase):
    """The main and its alt both keep the hostile Corporation at +5."""

    def setUp(self):
        super().setUp()
        self.alt_audit = CharacterAudit.objects.create(character=self.add_alt(ALT))
        self.add_contact(self.audit, 5)
        self.add_contact(self.alt_audit, 5)
        snapshot.update()

    def add_contact(self, audit, standing, contact_id=HOSTILE_CORP):
        CharacterContact.objects.create(
            id=audit.character.character_id * 10 + CharacterContact.objects.count(),
            character=audit, contact_id=contact_id, contact_type="corporation",
            contact_name=eve_name(contact_id, "corporation"), standing=standing,
        )

    def review(self, key=f"{HOSTILE_CORP}:5", cleared=True, note="Agreed"):
        FindingReview.objects.create(
            alliance_id=ALLIANCE_ID, kind=markers.CONTACTS, main_id=self.main.character_id, key=key,
            cleared=cleared, note=note,
        )

    def report_marker(self):
        report = snapshot.Report(snapshot.current(), (), {}, snapshot.finding_reviews(ALLIANCE_ID))
        suspect = next((suspect for suspect in report.tile(2001).suspects if suspect.user_id == self.user.pk), None)
        return suspect.markers.get(markers.CONTACTS) if suspect else None


class TestRows(FindingTestCase):
    def test_should_show_one_row_per_contact_and_standing_with_the_mains_characters(self):
        (row,) = self.report_marker().rows

        self.assertEqual(row["characters"], [self.main.character_name, f"Char {ALT}"])
        self.assertEqual((row["contact"], row["standing"], row["key"]), ("Bad Corp", "5", f"{HOSTILE_CORP}:5"))
        self.assertEqual(self.report_marker().count, 1)

    def test_should_show_another_standing_as_a_row_of_its_own(self):
        CharacterContact.objects.filter(character=self.alt_audit).update(standing=10)
        snapshot.update()

        self.assertEqual(sorted(row["standing"] for row in self.report_marker().rows), ["10", "5"])

    def test_should_name_the_contacts_corporation(self):
        (row,) = self.report_marker().rows

        self.assertEqual(row["category"], "corporation")
        self.assertEqual(row["corporation"], {"name": "Bad Corp", "standing": "-10.0"})
        self.assertTrue(self.report_marker().affiliated)

    def test_should_name_the_standing_that_makes_the_contact_hostile(self):
        (row,) = self.report_marker().rows

        self.assertEqual(row["reference"], {"standing": "-10.0", "sources": [["Us", "-10.0"]]})

    def test_should_take_the_corporations_standing_for_a_contact_hostile_through_it(self):
        CharacterContact.objects.create(
            id=1, character=self.audit, contact_id=HOSTILE_MEMBER, contact_type="character",
            contact_name=eve_name(HOSTILE_MEMBER), standing=10,
        )
        snapshot.update()

        row = next(row for row in self.report_marker().rows if row["contact_id"] == HOSTILE_MEMBER)

        self.assertEqual(row["reference"], {"standing": "-10.0", "sources": [["Us", "-10.0"]]})

    def test_should_pair_each_character_with_its_id(self):
        (row,) = self.report_marker().rows

        self.assertEqual(
            row["named_characters"], [(self.main.character_id, self.main.character_name), (ALT, f"Char {ALT}")]
        )


class TestReviewedReport(FindingTestCase):
    def test_should_drop_the_marker_once_the_contact_is_cleared(self):
        self.review()

        self.assertIsNone(self.report_marker())

    def test_should_list_the_cleared_contact_at_the_foot_of_the_corporation_page(self):
        self.review(note="Old friend")
        report = snapshot.Report(snapshot.current(), (), {}, snapshot.finding_reviews(ALLIANCE_ID))

        (cleared,) = report.tile(2001).cleared
        (row,) = cleared["rows"]

        self.assertEqual(cleared["main"].character_id, self.main.character_id)
        self.assertEqual((row["finding"], row["note"], row["killmail_id"]), ("Bad Corp (5)", "Old friend", None))

    def test_should_still_count_a_contact_with_a_note_only(self):
        self.review(cleared=False, note="Asked him")

        marker = self.report_marker()

        self.assertEqual(marker.count, 1)
        self.assertEqual(marker.rows[0]["note"], "Asked him")

    def test_should_clear_an_alt_that_shows_the_same_contact_later(self):
        # the user's rule: the review holds for the main, not for the characters ticked
        self.review()
        third = CharacterAudit.objects.create(character=self.add_alt(5002))
        self.add_contact(third, 5)
        snapshot.update()

        self.assertIsNone(self.report_marker())

    def test_should_reopen_the_contact_at_another_standing(self):
        self.review()
        CharacterContact.objects.filter(character=self.alt_audit).update(standing=10)
        snapshot.update()

        marker = self.report_marker()

        self.assertEqual(marker.count, 1)
        rows = {row["standing"]: row for row in marker.rows}
        self.assertTrue(rows["5"]["cleared"])
        self.assertFalse(rows["10"]["cleared"])

    def test_should_ignore_a_review_of_another_alliance(self):
        FindingReview.objects.create(
            alliance_id=OTHER_ALLIANCE_ID, kind=markers.CONTACTS, main_id=self.main.character_id,
            key=f"{HOSTILE_CORP}:5", cleared=True, note="Agreed",
        )

        self.assertEqual(self.report_marker().count, 1)


class TestReviewedApi(FindingTestCase):
    def test_should_leave_out_the_characters_of_a_cleared_contact(self):
        self.review()

        self.assertNotIn(ALT, api.character_markers())

    def test_should_keep_the_characters_of_an_open_contact(self):
        self.assertEqual(api.character_markers()[ALT], [markers.CONTACTS])


class TestFindingNote(FindingTestCase):
    def setUp(self):
        super().setUp()
        self.viewer = make_user("viewer", VIEW_SUSPECTS)
        self.client.force_login(self.viewer)

    def post(self, **fields):
        data = {"kind": markers.CONTACTS, "main_id": self.main.character_id, "key": f"{HOSTILE_CORP}:5"}
        return self.client.post(reverse("eos_spy_network:finding_note"), {**data, **fields})

    def test_should_store_the_note_and_the_tick(self):
        response = self.post(note="  Fleet   fight ", cleared="1")

        self.assertEqual(response.json(), {"note": "Fleet fight", "cleared": True})
        review = FindingReview.objects.get()
        self.assertEqual((review.alliance_id, review.cleared, review.reviewed_by), (ALLIANCE_ID, True, self.viewer))

    def test_should_change_the_one_review_of_a_finding(self):
        self.post(note="Agreed", cleared="1")

        self.post(note="Agreed")

        self.assertFalse(FindingReview.objects.get().cleared)

    def test_should_refuse_to_clear_without_a_note(self):
        self.assertEqual(self.post(note="  ", cleared="1").status_code, 400)
        self.assertFalse(FindingReview.objects.exists())

    def test_should_clear_without_a_note_for_an_admin(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

        self.assertEqual(self.post(note="", cleared="1").json(), {"note": "", "cleared": True})
        self.assertTrue(FindingReview.objects.get().cleared)

    def test_should_not_store_a_finding_the_result_does_not_hold(self):
        # a review ahead of its finding would clear it before anyone saw it
        self.assertEqual(self.post(key="1:5", note="Agreed", cleared="1").status_code, 404)
        self.assertFalse(FindingReview.objects.exists())
        self.assertFalse(ReviewLog.objects.exists())

    def test_should_not_store_for_another_main(self):
        self.assertEqual(self.post(main_id=1, note="Agreed").status_code, 404)
        self.assertFalse(FindingReview.objects.exists())

    def test_should_refuse_a_kind_without_reviews(self):
        self.assertEqual(self.post(kind=markers.MAILS, note="Agreed").status_code, 400)

    def test_should_refuse_a_main_that_is_no_number(self):
        self.assertEqual(self.post(main_id="x", note="Agreed").status_code, 400)

    def test_should_not_store_without_an_alliance(self):
        configure(alliance_id=None)

        self.assertEqual(self.post(note="Agreed").status_code, 404)

    def test_should_need_view_suspects(self):
        self.client.force_login(make_user("nobody"))

        self.assertEqual(self.post(note="Agreed", cleared="1").status_code, 302)
        self.assertFalse(FindingReview.objects.exists())

    def test_should_show_the_contact_with_its_tick_on_the_corporation_page(self):
        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, f'data-eos-spy-network-kill-key="{HOSTILE_CORP}:5"')
        self.assertContains(response, f'data-eos-spy-network-kill-main="{self.main.character_id}"')
        self.assertContains(response, "data-eos-spy-network-finding-url")

    def test_should_link_the_contact_and_each_character_to_evewho(self):
        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, f'href="https://evewho.com/corporation/{HOSTILE_CORP}"')
        self.assertContains(response, f'href="https://evewho.com/character/{self.main.character_id}"')
        self.assertContains(response, f'href="https://evewho.com/character/{ALT}"')
        self.assertContains(response, "<td class=\"text-break text-danger fw-semibold\" data-order=\"Bad Corp\">")

    def test_should_show_the_reference_standing_next_to_the_suspects(self):
        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, "<th>Reference standing</th>")
        self.assertContains(response, "<th>Suspect standing</th>")
        self.assertContains(response, 'title="Us: -10" data-order="-10.0">-10</td>')

    def test_should_show_a_dash_for_a_snapshot_without_the_reference_standing(self):
        stored = snapshot.current()
        for marker in stored.data["corporations"][0]["suspects"][0]["markers"]:
            for row in marker.get("rows", []):
                row.pop("reference", None)
        stored.save()

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, '<td class="text-nowrap">–</td>')

    def test_should_show_a_cleared_contact_greyed_while_another_stays_open(self):
        # with every contact cleared the marker is gone; the open one keeps the table on the page
        CharacterContact.objects.filter(character=self.alt_audit).update(standing=10)
        snapshot.update()
        self.post(note="Fleet fight", cleared="1")

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, 'class="opacity-50"', count=1)
        self.assertContains(response, "Fleet fight")


class TestSettingsTab(FindingTestCase):
    """Every friendly hostile contact of the snapshot, the cleared ones too, for the admin to tick off."""

    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

    def get(self):
        return self.client.get(reverse("eos_spy_network:settings") + "?tab=contacts")

    def test_should_list_the_contact_with_its_main_and_tick(self):
        response = self.get()

        self.assertEqual(response.context["tab"], "contacts")
        self.assertContains(response, 'id="eos-spy-network-settings-contacts"')
        self.assertContains(response, f'data-eos-spy-network-kill-key="{HOSTILE_CORP}:5"')
        self.assertContains(response, f'data-eos-spy-network-kill-main="{self.main.character_id}"')
        self.assertContains(response, self.main.character_name)
        self.assertContains(response, "data-eos-spy-network-kill-admin")

    def test_should_show_the_reference_standing_next_to_the_suspects(self):
        response = self.get()

        self.assertContains(response, "<th>Reference standing</th>")
        self.assertContains(response, "<th>Suspect standing</th>")
        self.assertContains(response, 'title="Us: -10" data-order="-10.0">-10</td>')

    def test_should_keep_a_cleared_contact_greyed_with_who_cleared_it(self):
        self.client.post(
            reverse("eos_spy_network:finding_note"),
            {"kind": markers.CONTACTS, "main_id": self.main.character_id, "key": f"{HOSTILE_CORP}:5", "cleared": "1"},
        )

        response = self.get()

        self.assertContains(response, 'class="opacity-50"', count=1)
        self.assertContains(response, "Last changed by admin main")

    def test_should_ignore_a_review_of_another_alliance(self):
        FindingReview.objects.create(
            alliance_id=OTHER_ALLIANCE_ID, kind=markers.CONTACTS, main_id=self.main.character_id,
            key=f"{HOSTILE_CORP}:5", cleared=True, note="Elsewhere",
        )

        self.assertNotContains(self.get(), "Elsewhere")

    def test_should_say_so_without_a_snapshot_of_the_alliance(self):
        configure(alliance_id=OTHER_ALLIANCE_ID)

        response = self.get()

        self.assertEqual(response.context["contacts"], [])
        self.assertContains(response, "No friendly hostile contact found.")
