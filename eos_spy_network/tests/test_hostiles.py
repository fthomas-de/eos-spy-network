from decimal import Decimal

from eos_spy_network.hostiles import hostile_entities, save_sources, source_rows
from eos_spy_network.models import ContactSource

from .base import (
    ALLIANCE_ID,
    OTHER_ALLIANCE_ID,
    SpyTestCase,
    add_contact,
    add_token,
    configure,
    make_corporation,
)

ALLIANCE = ContactSource.ALLIANCE
CORPORATION = ContactSource.CORPORATION


class TestHostileEntities(SpyTestCase):
    def setUp(self):
        super().setUp()
        make_corporation(2001)
        ContactSource.objects.create(kind=ALLIANCE, entity_id=ALLIANCE_ID, name="Us")
        ContactSource.objects.create(kind=CORPORATION, entity_id=2001, name="Corp")

    def test_should_list_contacts_below_the_threshold(self):
        config = configure(hostile_below=Decimal("0"))
        add_contact(ALLIANCE, ALLIANCE_ID, 1, -10)
        add_contact(ALLIANCE, ALLIANCE_ID, 2, -0.1)
        add_contact(ALLIANCE, ALLIANCE_ID, 3, 0)
        add_contact(ALLIANCE, ALLIANCE_ID, 4, 5)

        self.assertEqual([hostile.id for hostile in hostile_entities(config)], [1, 2])

    def test_should_follow_a_changed_threshold(self):
        config = configure(hostile_below=Decimal("-5"))
        add_contact(ALLIANCE, ALLIANCE_ID, 1, -10)
        add_contact(ALLIANCE, ALLIANCE_ID, 2, -5)

        self.assertEqual([hostile.id for hostile in hostile_entities(config)], [1])

    def test_should_merge_an_entity_of_several_sources(self):
        config = configure()
        add_contact(ALLIANCE, ALLIANCE_ID, 1, -5)
        add_contact(CORPORATION, 2001, 1, -10)

        [hostile] = hostile_entities(config)

        self.assertEqual(hostile.standing, Decimal("-10"))
        self.assertEqual(hostile.sources, [("Corp", Decimal("-10")), ("Us", Decimal("-5"))])

    def test_should_count_one_negative_source_even_if_another_is_positive(self):
        config = configure()
        add_contact(ALLIANCE, ALLIANCE_ID, 1, 5)
        add_contact(CORPORATION, 2001, 1, -10)

        self.assertEqual([hostile.id for hostile in hostile_entities(config)], [1])

    def test_should_ignore_contacts_of_unticked_sources(self):
        config = configure()
        add_contact(CORPORATION, 2002, 1, -10)

        self.assertEqual(hostile_entities(config), [])

    def test_should_never_list_the_alliance_or_its_corporations(self):
        config = configure()
        add_contact(CORPORATION, 2001, ALLIANCE_ID, -10, "alliance")
        add_contact(ALLIANCE, ALLIANCE_ID, 2001, -10)
        add_contact(ALLIANCE, ALLIANCE_ID, 7, -10)

        self.assertEqual([hostile.id for hostile in hostile_entities(config)], [7])


class TestSourceRows(SpyTestCase):
    def test_should_offer_the_alliance_and_its_corporations(self):
        make_corporation(2002)
        make_corporation(2001)
        make_corporation(2999, alliance_id=OTHER_ALLIANCE_ID)
        config = configure()

        rows = source_rows(config)

        self.assertEqual(
            [row.key for row in rows],
            [f"alliance:{ALLIANCE_ID}", "corporation:2001", "corporation:2002"],
        )
        self.assertTrue(all(row.in_alliance and row.source is None for row in rows))

    def test_should_offer_nothing_without_an_alliance(self):
        config = configure(alliance_id=None)

        self.assertEqual(source_rows(config), [])

    def test_should_keep_a_ticked_corporation_that_left(self):
        config = configure()
        ContactSource.objects.create(kind=CORPORATION, entity_id=2999, name="Gone Corp")

        rows = source_rows(config)

        self.assertEqual([(row.key, row.in_alliance) for row in rows][-1], ("corporation:2999", False))

    def test_should_say_whether_aa_contacts_has_a_token(self):
        make_corporation(2001)
        make_corporation(2002)
        add_token(CORPORATION, 2001)
        config = configure()

        tokens = {row.key: row.has_token for row in source_rows(config)}

        self.assertEqual(
            tokens, {f"alliance:{ALLIANCE_ID}": False, "corporation:2001": True, "corporation:2002": False}
        )

    def test_should_count_contacts_and_hostiles(self):
        make_corporation(2001)
        config = configure()
        add_token(CORPORATION, 2001)
        add_contact(CORPORATION, 2001, 1, -10)
        add_contact(CORPORATION, 2001, 2, 10)

        row = [row for row in source_rows(config) if row.has_token][0]

        self.assertEqual((row.contact_count, row.hostile_count), (2, 1))


class TestSaveSources(SpyTestCase):
    def setUp(self):
        super().setUp()
        make_corporation(2001)
        make_corporation(2002)
        self.config = configure()

    def test_should_create_ticked_and_delete_unticked_sources(self):
        ContactSource.objects.create(kind=CORPORATION, entity_id=2002)

        changed = save_sources(source_rows(self.config), [f"alliance:{ALLIANCE_ID}", "corporation:2001"])

        self.assertTrue(changed)
        self.assertEqual(
            set(ContactSource.objects.values_list("kind", "entity_id", "name")),
            {("alliance", ALLIANCE_ID, f"Alliance {ALLIANCE_ID}"), ("corporation", 2001, "Corp 2001")},
        )

    def test_should_ignore_keys_that_were_not_offered(self):
        changed = save_sources(source_rows(self.config), ["corporation:9999", "alliance:1"])

        self.assertFalse(changed)
        self.assertFalse(ContactSource.objects.exists())

    def test_should_report_no_change_when_the_ticks_stay(self):
        ContactSource.objects.create(kind=CORPORATION, entity_id=2001, name="Corp 2001")

        self.assertFalse(save_sources(source_rows(self.config), ["corporation:2001"]))

    def test_should_take_over_a_new_corporation_name(self):
        source = ContactSource.objects.create(kind=CORPORATION, entity_id=2001, name="Old name")

        save_sources(source_rows(self.config), ["corporation:2001"])

        source.refresh_from_db()
        self.assertEqual(source.name, "Corp 2001")
