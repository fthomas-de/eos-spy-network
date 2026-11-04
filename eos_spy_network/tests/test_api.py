from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.utils.translation import override

from eos_spy_network import api, markers
from eos_spy_network.models import Snapshot

from .base import ALLIANCE_ID, OTHER_ALLIANCE_ID, SpyTestCase, configure


def marker(kind, *character_ids):
    return {"kind": kind, "count": 1, "details": [], "rows": [], "character_ids": list(character_ids)}


def store(*suspect_markers, alliance_id=ALLIANCE_ID):
    """A snapshot with one account per entry of ``suspect_markers`` (a list of markers each)."""
    suspects = [
        {
            "user_id": user_id,
            "main_id": user_id + 1000,
            "main_name": f"Main {user_id}",
            "corporation_id": 2001,
            "character_count": 2,
            "markers": stored,
        }
        for user_id, stored in enumerate(suspect_markers, 1)
    ]
    data = {
        "alliance_id": alliance_id,
        "alliance_name": f"Alliance {alliance_id}",
        "corporations": [{"id": 2001, "name": "Corp 2001", "ticker": "C2001", "mains": 2, "suspects": suspects}],
    }
    return Snapshot.objects.create(pk=1, built_at=timezone.now(), data=data)


class TestCharacterMarkers(SpyTestCase):
    def setUp(self):
        super().setUp()
        configure()

    def test_should_map_each_character_to_its_marker_kinds_in_page_order(self):
        store(
            # stored out of page order on purpose
            [marker(markers.MAILS, 501), marker(markers.MEMBERSHIP, 501, 502)],
            [marker(markers.CONTRACTS, 601)],
        )

        self.assertEqual(
            api.character_markers(),
            {501: [markers.MEMBERSHIP, markers.MAILS], 502: [markers.MEMBERSHIP], 601: [markers.CONTRACTS]},
        )

    def test_should_give_nothing_without_a_snapshot(self):
        self.assertEqual(api.character_markers(), {})

    def test_should_give_nothing_without_an_alliance(self):
        store([marker(markers.MEMBERSHIP, 501)])
        configure(alliance_id=None)

        self.assertEqual(api.character_markers(), {})

    def test_should_give_nothing_for_the_snapshot_of_another_alliance(self):
        store([marker(markers.MEMBERSHIP, 501)], alliance_id=OTHER_ALLIANCE_ID)

        self.assertEqual(api.character_markers(), {})

    def test_should_leave_out_switched_off_markers(self):
        store([marker(markers.MEMBERSHIP, 501), marker(markers.MAILS, 501, 502)])
        configure(disabled_markers=[markers.MAILS])

        self.assertEqual(api.character_markers(), {501: [markers.MEMBERSHIP]})

    def test_should_read_an_older_snapshot_without_characters(self):
        stored = marker(markers.MEMBERSHIP)
        del stored["character_ids"]
        store([stored])

        self.assertEqual(api.character_markers(), {})

    def test_should_read_the_configuration_and_the_snapshot_only(self):
        store([marker(markers.MEMBERSHIP, 501)])

        with CaptureQueriesContext(connection) as queries:
            api.character_markers()

        self.assertEqual(len(queries), 2)


class TestKinds(SpyTestCase):
    def test_should_give_the_kinds_in_page_order(self):
        self.assertEqual(
            api.KINDS,
            (markers.MEMBERSHIP, markers.CORP_CHANGES, markers.CONTACTS, markers.MAILS, markers.WALLET, markers.CONTRACTS),
        )


class TestTexts(SpyTestCase):
    def test_should_give_the_texts_of_the_pages(self):
        for kind in markers.KINDS:
            self.assertEqual(api.label(kind), markers.LABELS[kind])
            self.assertEqual(api.description(kind), markers.DESCRIPTIONS[kind])

    def test_should_translate_lazily(self):
        # taken before the request's language is known, as a module-level import would
        text = api.label(markers.MEMBERSHIP)

        with override("de"):
            self.assertNotEqual(str(text), "Hostile membership")
