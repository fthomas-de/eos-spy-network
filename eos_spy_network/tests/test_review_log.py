"""The log of every saved note and Cleared tick, and its settings tab."""

from importlib import import_module

from django.apps import apps
from django.urls import reverse
from django.utils import timezone

from eos_spy_network import markers
from eos_spy_network.models import BlueKill, FindingReview, ReviewLog

from .base import OTHER_ALLIANCE_ID, ALLIANCE_ID, make_user
from .test_finding_reviews import FindingTestCase
from .test_kill_reviews import ReviewTestCase
from .test_kills import ALT
from .test_markers import HOSTILE_CORP

VIEW_SUSPECTS = "eos_spy_network.view_suspects"
MANAGE_SETTINGS = "eos_spy_network.manage_settings"
CONTACT_KEY = f"{HOSTILE_CORP}:5"


class TestKillLog(ReviewTestCase):
    def setUp(self):
        super().setUp()
        self.viewer = make_user("viewer", VIEW_SUSPECTS)
        self.client.force_login(self.viewer)

    def post(self, **fields):
        return self.client.post(reverse("eos_spy_network:kill_note"), {"killmail_id": 1, "character_id": ALT, **fields})

    def test_should_log_each_save_with_the_state_before(self):
        self.post(note="Fleet fight", cleared="1")
        self.post(note="Not a fleet fight")

        first, second = ReviewLog.objects.order_by("id")
        self.assertEqual(
            (first.kind, first.character_id, first.key, first.cleared, first.note, first.previous_cleared),
            (markers.BLUE_KILLS, ALT, "1", True, "Fleet fight", False),
        )
        self.assertEqual(first.changed_by, self.viewer)
        self.assertEqual(
            (second.cleared, second.note, second.previous_cleared, second.previous_note),
            (False, "Not a fleet fight", True, "Fleet fight"),
        )

    def test_should_log_nothing_for_a_refused_save(self):
        self.post(note="", cleared="1")
        self.post(killmail_id=99, note="Agreed")

        self.assertFalse(ReviewLog.objects.exists())


class TestFindingLog(FindingTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

    def post(self, **fields):
        data = {"kind": markers.CONTACTS, "main_id": self.main.character_id, "key": CONTACT_KEY}
        return self.client.post(reverse("eos_spy_network:finding_note"), {**data, **fields})

    def test_should_log_each_save_with_the_state_before(self):
        self.post(note="Agreed", cleared="1")
        self.post(note="")

        first, second = ReviewLog.objects.order_by("id")
        self.assertEqual(
            (first.kind, first.character_id, first.key, first.previous_cleared, first.previous_note),
            (markers.CONTACTS, self.main.character_id, CONTACT_KEY, None, ""),
        )
        self.assertEqual(
            (second.cleared, second.note, second.previous_cleared, second.previous_note), (False, "", True, "Agreed")
        )

    def test_should_log_nothing_for_a_refused_save(self):
        self.post(note="", cleared="1")

        self.assertFalse(ReviewLog.objects.exists())


class TestLogTab(FindingTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

    def get(self):
        return self.client.get(reverse("eos_spy_network:settings") + "?tab=log")

    def test_should_list_a_save_with_its_main_contact_and_who(self):
        self.client.post(
            reverse("eos_spy_network:finding_note"),
            {"kind": markers.CONTACTS, "main_id": self.main.character_id, "key": CONTACT_KEY, "note": "Spai check"},
        )

        response = self.get()

        self.assertEqual(response.context["tab"], "log")
        [entry] = response.context["log"]
        self.assertEqual((entry.main_name, entry.finding, entry.label), (self.main.character_name, "Bad Corp", "Friendly to hostiles"))
        self.assertContains(response, "Spai check")
        self.assertContains(response, "admin main")

    def log(self, character_id, changed_by):
        ReviewLog.objects.create(
            alliance_id=ALLIANCE_ID, kind=markers.CONTACTS, character_id=character_id, key=CONTACT_KEY,
            cleared=True, note="Logged note", changed_at=timezone.now(), changed_by=changed_by,
        )

    def test_should_mark_a_save_on_the_reviewers_own_account(self):
        admin = make_user("own", MANAGE_SETTINGS, VIEW_SUSPECTS)
        self.client.force_login(admin)
        self.log(admin.profile.main_character.character_id, admin)

        self.assertContains(self.get(), "Own account")

    def test_should_not_mark_a_save_on_another_account(self):
        admin = make_user("own", MANAGE_SETTINGS, VIEW_SUSPECTS)
        self.client.force_login(admin)
        self.log(self.main.character_id, admin)

        response = self.get()

        self.assertContains(response, "Logged note")
        self.assertNotContains(response, "Own account")

    def test_should_keep_the_log_from_a_viewer_without_view_suspects(self):
        self.log(self.main.character_id, None)
        self.client.force_login(make_user("settings", MANAGE_SETTINGS))

        response = self.get()

        self.assertNotContains(response, "Logged note")
        self.assertEqual(response.context["log"], [])

    def test_should_leave_out_another_alliance(self):
        ReviewLog.objects.create(
            alliance_id=OTHER_ALLIANCE_ID, kind=markers.CONTACTS, character_id=1, key="1:5", cleared=True,
            note="Elsewhere", changed_at=timezone.now(),
        )

        self.assertEqual(self.get().context["log"], [])


class TestKillLogTab(ReviewTestCase):
    def test_should_name_the_victim_and_the_main_of_the_character(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))
        self.client.post(reverse("eos_spy_network:kill_note"), {"killmail_id": 1, "character_id": ALT, "note": "Ok"})

        response = self.client.get(reverse("eos_spy_network:settings") + "?tab=log")

        [entry] = response.context["log"]
        self.assertEqual((entry.main_id, entry.main_name, entry.finding), (self.main.character_id, self.main.character_name, "Name 90000001"))
        # one in the Blue kills tab, one in the log
        self.assertContains(response, 'href="https://zkillboard.com/kill/1/"', count=2)


class TestSeed(ReviewTestCase):
    """The migration's copy of the reviews made before the log."""

    def test_should_copy_one_entry_per_saved_group_and_finding(self):
        # one save of a main's two characters on killmail 1, as kill_note writes it
        kill = BlueKill.objects.get(killmail_id=1)
        BlueKill.objects.create(
            **{field: getattr(kill, field) for field in ("alliance_id", "killmail_id", "time", "reason")},
            character_id=self.main.character_id,
        )
        at = timezone.now()
        BlueKill.objects.filter(killmail_id=1).update(cleared=True, note="Agreed", reviewed_at=at)
        FindingReview.objects.create(
            alliance_id=ALLIANCE_ID, kind=markers.CONTACTS, main_id=1, key="1:5", note="Watched", reviewed_at=at
        )
        FindingReview.objects.create(alliance_id=ALLIANCE_ID, kind=markers.CONTACTS, main_id=2, key="2:5")

        import_module("eos_spy_network.migrations.0010_review_log").seed(apps, None)

        self.assertEqual(
            sorted(ReviewLog.objects.values_list("kind", "key", "cleared", "note", "previous_cleared")),
            [(markers.BLUE_KILLS, "1", True, "Agreed", None), (markers.CONTACTS, "1:5", False, "Watched", None)],
        )
