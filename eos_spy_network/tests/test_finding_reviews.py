"""The note and the cleared tick of a friendly hostile contact: per main, contact and standing."""

from corptools.models import CharacterAudit, CharacterContact

from django.urls import reverse

from eos_spy_network import api, markers, snapshot
from eos_spy_network.models import FindingReview

from .base import ALLIANCE_ID, OTHER_ALLIANCE_ID, configure, make_user
from .test_markers import HOSTILE_CORP, MarkerTestCase, eve_name

VIEW_SUSPECTS = "eos_spy_network.view_suspects"
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


class TestReviewedReport(FindingTestCase):
    def test_should_drop_the_marker_once_the_contact_is_cleared(self):
        self.review()

        self.assertIsNone(self.report_marker())

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

    def test_should_show_a_cleared_contact_greyed_while_another_stays_open(self):
        # with every contact cleared the marker is gone; the open one keeps the table on the page
        CharacterContact.objects.filter(character=self.alt_audit).update(standing=10)
        snapshot.update()
        self.post(note="Fleet fight", cleared="1")

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, 'class="opacity-50"', count=1)
        self.assertContains(response, "Fleet fight")
