from datetime import timedelta
from unittest.mock import patch

from aa_contacts.models import AllianceContact
from eveuniverse.models import EveEntity
from killtracker.models import EveKillmail, EveKillmailAttacker

from django.urls import reverse
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership

from eos_spy_network import markers, snapshot
from eos_spy_network.models import BlueKill, ContactSource

from .base import ALLIANCE_ID, OTHER_ALLIANCE_ID, SpyTestCase, add_contact, add_token, configure, make_character, make_corporation, make_user

BLUE_ALLIANCE = 99000010
BLUE_CORP = 98000010
NEUTRAL_CORP = 98000011
ALT = 5001
VIEW_SUSPECTS = "eos_spy_network.view_suspects"
NOT_INSTALLED = "eos_spy_network.killmails.is_installed"


def entity(eve_id, category, name=None):
    return EveEntity.objects.get_or_create(
        id=eve_id, defaults={"name": f"Name {eve_id}" if name is None else name, "category": category}
    )[0]


def add_killmail(
    killmail_id, attacker_ids, victim_id=None, corporation_id=NEUTRAL_CORP, alliance_id=None, days_ago=1, value=None
):
    """A killmail as killtracker stores it: the victim on the killmail, one row per attacker."""
    killmail = EveKillmail.objects.create(
        id=killmail_id,
        time=timezone.now() - timedelta(days=days_ago),
        character=entity(victim_id, EveEntity.CATEGORY_CHARACTER) if victim_id else None,
        corporation=entity(corporation_id, EveEntity.CATEGORY_CORPORATION),
        alliance=entity(alliance_id, EveEntity.CATEGORY_ALLIANCE) if alliance_id else None,
        ship_type=entity(587, EveEntity.CATEGORY_INVENTORY_TYPE, "Rifter"),
        total_value=value,
    )
    for attacker_id in attacker_ids:
        EveKillmailAttacker.objects.create(
            killmail=killmail, character=entity(attacker_id, EveEntity.CATEGORY_CHARACTER)
        )
    return killmail


class KillTestCase(SpyTestCase):
    """A member with an alt; the Alliance holds a blue Alliance (+10) and a blue Corporation (+5)."""

    def setUp(self):
        super().setUp()
        configure()
        make_corporation(2001)
        add_token(ContactSource.ALLIANCE, ALLIANCE_ID)
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, BLUE_ALLIANCE, 10, contact_type="alliance")
        add_contact(ContactSource.ALLIANCE, ALLIANCE_ID, BLUE_CORP, 5)

        self.user = make_user("suspect")
        self.main = self.user.profile.main_character
        alt = make_character(ALT)
        CharacterOwnership.objects.create(user=self.user, character=alt, owner_hash=f"hash-{ALT}")

    def marker(self):
        (tile,) = markers.corporation_tiles(corporation_id=2001)
        suspect = next((suspect for suspect in tile.suspects if suspect.user_id == self.user.pk), None)
        return suspect.markers.get(markers.BLUE_KILLS) if suspect else None


class TestBlueKills(KillTestCase):
    def test_should_mark_an_awox_on_a_member_of_the_alliance(self):
        add_killmail(1, [ALT], victim_id=90000001, corporation_id=2002, alliance_id=ALLIANCE_ID)

        marker = self.marker()

        self.assertEqual(marker.count, 1)
        self.assertEqual(marker.character_ids, {ALT})
        (row,) = marker.rows
        self.assertEqual(row["reason"], markers.AWOX)
        self.assertEqual(row["victim"], "Name 90000001")
        self.assertEqual(row["ship"], "Rifter")
        self.assertEqual(row["killmail_id"], 1)

    def test_should_mark_a_kill_of_a_blue_alliance_with_its_standing(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=BLUE_ALLIANCE)

        (row,) = self.marker().rows

        self.assertEqual(row["reason"], markers.BLUE)
        self.assertEqual(row["standing"], "10")

    def test_should_mark_a_kill_of_a_blue_corporation_at_the_threshold(self):
        add_killmail(1, [ALT], victim_id=90000001, corporation_id=BLUE_CORP)

        self.assertEqual(self.marker().rows[0]["standing"], "5")

    def test_should_ignore_a_standing_below_the_threshold(self):
        configure(blue_from=6)
        add_killmail(1, [ALT], victim_id=90000001, corporation_id=BLUE_CORP)

        self.assertIsNone(self.marker())

    def test_should_ignore_a_blue_of_a_corporation_source(self):
        # only the Alliance's own contacts make a blue, whatever sources are ticked
        ContactSource.objects.create(kind=ContactSource.CORPORATION, entity_id=2001, name="Own Corp")
        add_token(ContactSource.CORPORATION, 2001)
        add_contact(ContactSource.CORPORATION, 2001, NEUTRAL_CORP, 10)
        add_killmail(1, [ALT], victim_id=90000001, corporation_id=NEUTRAL_CORP)

        self.assertIsNone(self.marker())

    def test_should_ignore_kills_of_neutrals(self):
        add_killmail(1, [ALT], victim_id=90000001)

        self.assertIsNone(self.marker())

    def test_should_ignore_kills_before_the_time_frame(self):
        configure(lookback_days=30)
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID, days_ago=31)

        self.assertIsNone(self.marker())

    def test_should_count_a_killmail_with_two_own_characters_once(self):
        add_killmail(1, [ALT, self.main.character_id], victim_id=90000001, alliance_id=ALLIANCE_ID)

        marker = self.marker()

        self.assertEqual(marker.count, 1)
        self.assertEqual(marker.character_ids, {ALT, self.main.character_id})
        self.assertEqual(len(marker.rows), 2)

    def test_should_list_the_latest_kill_first(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID, days_ago=5)
        add_killmail(2, [ALT], victim_id=90000002, alliance_id=ALLIANCE_ID, days_ago=1)

        self.assertEqual([row["killmail_id"] for row in self.marker().rows], [2, 1])

    def test_should_take_the_contact_name_of_an_unresolved_entity(self):
        # killtracker stores the killmail before it resolves the names
        make_corporation(BLUE_CORP, alliance_id=None)
        add_killmail(1, [ALT], corporation_id=BLUE_CORP)
        EveEntity.objects.filter(id=BLUE_CORP).update(name="")

        marker = self.marker()

        # a structure has no character: its Corporation names the victim
        self.assertEqual(marker.rows[0]["victim"], "")
        self.assertEqual(marker.rows[0]["corporation"], f"Corp {BLUE_CORP}")
        self.assertEqual(marker.details, {f"Corp {BLUE_CORP}"})

    def test_should_mark_blue_kills_without_any_hostile(self):
        # no contact source is ticked: the other markers find nothing, the blue kills still count
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID)

        self.assertEqual(ContactSource.objects.count(), 0)
        self.assertEqual(self.marker().count, 1)

    def test_should_find_nothing_without_killtracker(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID)

        with patch(NOT_INSTALLED, return_value=False):
            self.assertIsNone(self.marker())


class TestOwnKills(KillTestCase):
    """A kill between two characters of one account is no awox."""

    def test_should_not_copy_a_kill_of_an_own_character(self):
        add_killmail(1, [ALT], victim_id=self.main.character_id, corporation_id=2001, alliance_id=ALLIANCE_ID)

        self.assertIsNone(self.marker())
        self.assertFalse(BlueKill.objects.exists())

    def test_should_leave_out_an_own_kill_copied_before(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID)
        self.marker()
        BlueKill.objects.update(victim_id=self.main.character_id)
        EveKillmail.objects.all().delete()

        self.assertIsNone(self.marker())

    def test_should_keep_the_kill_of_another_account(self):
        other = make_user("other").profile.main_character
        add_killmail(1, [ALT], victim_id=other.character_id, corporation_id=2001, alliance_id=ALLIANCE_ID)

        self.assertEqual(self.marker().count, 1)


class TestCopiedKills(KillTestCase):
    """killtracker deletes its killmails after a few days; the copies in BlueKill keep the marker."""

    def test_should_keep_a_kill_killtracker_deleted(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID)
        self.marker()
        EveKillmail.objects.all().delete()

        self.assertEqual(self.marker().count, 1)

    def test_should_copy_a_kill_once(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID)
        self.marker()

        marker = self.marker()

        self.assertEqual(BlueKill.objects.count(), 1)
        self.assertEqual(len(marker.rows), 1)

    def test_should_keep_the_standing_of_the_time_it_was_copied(self):
        # still blue, so copied again: the copy must not take the new standing
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=BLUE_ALLIANCE)
        self.marker()
        AllianceContact.objects.filter(contact_id=BLUE_ALLIANCE).update(standing=7)

        self.assertEqual(self.marker().rows[0]["standing"], "10")

    def test_should_take_the_names_killtracker_resolved_later(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID)
        EveEntity.objects.filter(id=90000001).update(name="")
        self.assertEqual(self.marker().rows[0]["victim"], "90000001")
        EveEntity.objects.filter(id=90000001).update(name="Resolved")

        self.assertEqual(self.marker().rows[0]["victim"], "Resolved")

    def test_should_leave_out_copies_before_the_time_frame(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID, days_ago=60)
        self.marker()
        configure(lookback_days=30)

        self.assertIsNone(self.marker())

    def test_should_leave_out_the_kills_of_another_alliance(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID)
        self.marker()
        BlueKill.objects.update(alliance_id=OTHER_ALLIANCE_ID)
        EveKillmail.objects.all().delete()

        self.assertIsNone(self.marker())


class TestMinimumValue(KillTestCase):
    """A kill below the minimum value, in million ISK, does not count; one without a value does."""

    def setUp(self):
        super().setUp()
        configure(min_kill_value=1)

    def test_should_copy_the_value(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID, value=2_500_000.5)
        self.marker()

        self.assertEqual(BlueKill.objects.get().value, 2_500_000.5)

    def test_should_ignore_a_kill_below_the_minimum(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID, value=10_000)

        self.assertIsNone(self.marker())

    def test_should_count_a_kill_at_the_minimum(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID, value=1_000_000)

        self.assertEqual(self.marker().count, 1)

    def test_should_count_a_kill_without_a_value(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID)

        self.assertEqual(self.marker().count, 1)

    def test_should_count_every_kill_at_zero(self):
        configure(min_kill_value=0)
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID, value=10_000)

        self.assertEqual(self.marker().count, 1)

    def test_should_give_an_older_copy_its_value(self):
        add_killmail(1, [ALT], victim_id=90000001, alliance_id=ALLIANCE_ID, value=10_000)
        self.marker()
        BlueKill.objects.update(value=None)

        self.assertIsNone(self.marker())
        self.assertEqual(BlueKill.objects.get().value, 10_000)


class TestKillsPage(KillTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

    def test_should_link_the_kill_on_zkillboard(self):
        add_killmail(4711, [ALT], victim_id=90000001, alliance_id=BLUE_ALLIANCE)
        snapshot.update()

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, "Blue kills")
        self.assertContains(response, "https://zkillboard.com/kill/4711/")
        self.assertContains(response, "Blue (10)")

    def test_should_show_the_value_in_million(self):
        add_killmail(4711, [ALT], victim_id=90000001, alliance_id=BLUE_ALLIANCE, value=1_234_567_890)
        add_killmail(4712, [ALT], victim_id=90000001, alliance_id=BLUE_ALLIANCE)
        snapshot.update()

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, "1,234.6 M")
        # the kill zKillboard sent no value for
        self.assertContains(response, "<td class=\"text-nowrap\">–</td>", html=True)

    @patch("eos_spy_network.killmails.is_storing", return_value=False)
    def test_should_say_that_killtracker_stores_no_killmails(self, _storing):
        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "killtracker does not store its killmails")

    @patch("eos_spy_network.killmails.is_storing", return_value=False)
    def test_should_not_mention_killtracker_with_the_marker_switched_off(self, _storing):
        configure(disabled_markers=[markers.BLUE_KILLS])

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertNotContains(response, "killtracker")

    def test_should_say_that_killtracker_is_missing(self):
        with patch(NOT_INSTALLED, return_value=False):
            response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "killtracker is not installed")
