"""The note and the cleared tick of ISK and contracts: per own character and counterpart a case, summed; a case
cleared once keeps the entries it held, anything else is a new case (user, 2026-11-27)."""

from datetime import timedelta

from corptools.models import CharacterAudit, CorporationHistory, MailMessage, MailRecipient

from django.urls import reverse
from django.utils import timezone

from allianceauth.authentication.models import OwnershipRecord

from eos_spy_network import api, markers, snapshot
from eos_spy_network.models import FindingReview, ReviewLog

from .base import ALLIANCE_ID, configure, make_user
from .test_markers import HOSTILE_CORP, HOSTILE_MEMBER, MarkerTestCase, TestContracts, TestWallet, eve_name

VIEW_SUSPECTS = "eos_spy_network.view_suspects"
MANAGE_SETTINGS = "eos_spy_network.manage_settings"


class DealingTestCase(MarkerTestCase):
    """Two donations between the main and the hostile Corporation, three days and one day ago."""

    add_entry = TestWallet.add_entry
    add_contract = TestContracts.add_contract

    def setUp(self):
        super().setUp()
        self.add_entry(1, HOSTILE_CORP, self.main.character_id, amount=500, days_ago=3)
        self.add_entry(2, self.main.character_id, HOSTILE_CORP, amount=-200, days_ago=1)
        snapshot.update()
        self.prefix = f"{self.main.character_id}:{HOSTILE_CORP}:"

    def review(self, number=0, cleared=True, note="Agreed", items=(1, 2), kind=markers.WALLET):
        FindingReview.objects.create(
            alliance_id=ALLIANCE_ID, kind=kind, main_id=self.main.character_id, key=f"{self.prefix}{number}",
            cleared=cleared, note=note, items=list(items),
        )

    def report(self):
        return snapshot.Report(snapshot.current(), (), {}, snapshot.finding_reviews(ALLIANCE_ID))

    def report_marker(self, kind=markers.WALLET):
        suspects = self.report().tile(2001).suspects
        suspect = next((suspect for suspect in suspects if suspect.user_id == self.user.pk), None)
        return suspect.markers.get(kind) if suspect else None

    def cases(self):
        return {row["key"]: row for row in self.report_marker().rows}


class TestCases(DealingTestCase):
    def test_should_sum_up_one_open_case_with_each_entry(self):
        (row,) = self.report_marker().rows

        self.assertEqual(
            (row["key"], row["count"], row["isk"], row["cleared"]), (f"{self.prefix}0", 2, "700.00", False)
        )
        self.assertEqual(
            [entry[1:] for entry in row["entries"]],
            [("player donation", "200.00", None), ("player donation", "500.00", None)],
        )
        self.assertEqual(row["day_open"], 1)

    def test_should_drop_the_marker_once_the_case_is_cleared(self):
        self.review()

        self.assertIsNone(self.report_marker())
        (cleared,) = self.report().tile(2001).cleared
        self.assertEqual([(row["finding"], row["note"]) for row in cleared["rows"]], [("Bad Corp", "Agreed")])

    def test_should_open_a_new_case_for_an_entry_after_the_clear(self):
        self.review()
        self.add_entry(3, HOSTILE_CORP, self.main.character_id, amount=50)
        snapshot.update()

        cases = self.cases()

        self.assertEqual(self.report_marker().count, 1)
        self.assertEqual((cases[f"{self.prefix}1"]["count"], cases[f"{self.prefix}1"]["cleared"]), (1, False))
        self.assertEqual((cases[f"{self.prefix}0"]["count"], cases[f"{self.prefix}0"]["cleared"]), (2, True))
        # the open one first, the cleared one folded below
        self.assertEqual([row["cleared"] for row in self.report_marker().rows], [False, True])

    def test_should_open_a_new_case_for_an_entry_fetched_late_with_an_older_date(self):
        # corptools fetches the journal with a delay: a time split would hide this entry in the cleared case
        self.review()
        self.add_entry(3, HOSTILE_CORP, self.main.character_id, amount=50, days_ago=2)
        snapshot.update()

        self.assertEqual(self.cases()[f"{self.prefix}1"]["count"], 1)

    def test_should_keep_the_entries_of_a_case_ticked_off_again(self):
        self.review(cleared=False, note="")
        self.add_entry(3, HOSTILE_CORP, self.main.character_id, amount=50)
        snapshot.update()

        cases = self.cases()

        self.assertEqual((cases[f"{self.prefix}0"]["count"], cases[f"{self.prefix}1"]["count"]), (2, 1))
        self.assertEqual(self.report_marker().count, 3)

    def test_should_keep_the_note_of_the_open_case(self):
        self.review(cleared=False, note="Asked him", items=())

        (row,) = self.report_marker().rows

        self.assertEqual((row["note"], row["count"]), ("Asked him", 2))

    def test_should_leave_a_snapshot_without_items_unreviewed(self):
        stored = snapshot.current()
        for marker in stored.data["corporations"][0]["suspects"][0]["markers"]:
            for row in marker["rows"]:
                row.pop("items")
        stored.save()
        self.review()

        (row,) = self.report_marker().rows

        self.assertNotIn("key", row)


class TestApi(DealingTestCase):
    def test_should_leave_out_a_cleared_case(self):
        self.review()

        self.assertNotIn(self.main.character_id, api.character_markers())

    def test_should_keep_an_open_case(self):
        self.assertEqual(api.character_markers()[self.main.character_id], [markers.WALLET])


class TestFindingNote(DealingTestCase):
    def setUp(self):
        super().setUp()
        self.viewer = make_user("viewer", VIEW_SUSPECTS)
        self.client.force_login(self.viewer)

    def post(self, **fields):
        data = {"kind": markers.WALLET, "main_id": self.main.character_id, "key": f"{self.prefix}0"}
        return self.client.post(reverse("eos_spy_network:finding_note"), {**data, **fields})

    def test_should_fix_the_entries_of_the_case_at_the_first_tick(self):
        self.assertEqual(self.post(note="Trade", cleared="1").json(), {"note": "Trade", "cleared": True})

        self.assertEqual(sorted(FindingReview.objects.get().items), [1, 2])

    def test_should_keep_the_entries_when_ticked_off_again(self):
        self.post(note="Trade", cleared="1")
        self.add_entry(3, HOSTILE_CORP, self.main.character_id, amount=50)
        snapshot.update()

        self.post(note="Trade")

        self.assertEqual(sorted(FindingReview.objects.get().items), [1, 2])

    def test_should_fix_no_entries_with_a_note_only(self):
        self.post(note="Asked him")

        self.assertEqual(FindingReview.objects.get().items, [])

    def test_should_clear_every_open_case_of_a_day(self):
        last = (timezone.now() - timedelta(days=1)).date().isoformat()

        response = self.post(key="", date=last, note="Trade", cleared="1")

        self.assertEqual(response.json(), {"note": "Trade", "cleared": True, "count": 1})
        self.assertIsNone(self.report_marker())
        self.assertEqual(ReviewLog.objects.get().key, f"{self.prefix}0")

    def test_should_not_find_a_day_without_an_open_case(self):
        older = (timezone.now() - timedelta(days=3)).date().isoformat()

        self.assertEqual(self.post(key="", date=older, note="Trade", cleared="1").status_code, 404)

    def test_should_not_store_a_case_the_result_does_not_hold(self):
        self.assertEqual(self.post(key=f"{self.prefix}1", note="Trade", cleared="1").status_code, 404)
        self.assertFalse(FindingReview.objects.exists())

    def test_should_clear_a_contract_with_its_contract_ids(self):
        self.add_contract(7, self.main.character_id, 2001, HOSTILE_CORP, price=1000)
        snapshot.update()

        self.post(kind=markers.CONTRACTS, note="Sold", cleared="1")

        self.assertEqual(FindingReview.objects.get(kind=markers.CONTRACTS).items, [7])
        self.assertIsNone(self.report_marker(markers.CONTRACTS))

    def test_should_show_the_case_with_its_tick_day_row_and_entries_on_the_corporation_page(self):
        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, f'data-eos-spy-network-kill-key="{self.prefix}0"')
        self.assertContains(response, f'data-eos-spy-network-kill-kind="{markers.WALLET}"', count=2)
        last = (timezone.now() - timedelta(days=1)).date().isoformat()
        self.assertContains(response, f'data-eos-spy-network-kill-day="{last}"', count=1)
        self.assertContains(response, "data-eos-spy-network-items", count=1)
        self.assertContains(response, "<td>player donation</td>", count=2)
        self.assertContains(response, "eos_spy_network/js/items.")

    def test_should_fold_a_cleared_case_under_the_open_one(self):
        self.post(note="Trade", cleared="1")
        self.add_entry(3, HOSTILE_CORP, self.main.character_id, amount=50)
        snapshot.update()

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        folded = f"eos-spy-network-cleared-{self.main.character_id}-{markers.WALLET}"
        self.assertContains(response, f'<tr class="opacity-50 collapse {folded}">', count=1)
        self.assertContains(response, f'data-bs-target=".{folded}"', count=1)


class MailTestCase(DealingTestCase):
    """Besides the donations: a mail from the hostile member two days ago, and one to it a day ago."""

    def setUp(self):
        super().setUp()
        self.add_mail(1, 11, HOSTILE_MEMBER, "Hello", days_ago=2)
        self.add_mail(2, 12, self.main.character_id, "Re: Hello", days_ago=1, recipients=[HOSTILE_MEMBER])
        snapshot.update()
        self.prefix = f"{self.main.character_id}:{HOSTILE_MEMBER}:"

    def add_mail(self, id_key, mail_id, from_id, subject, days_ago=None, recipients=()):
        mail = MailMessage.objects.create(
            id_key=id_key, character=self.audit, mail_id=mail_id, from_id=from_id, subject=subject,
            timestamp=None if days_ago is None else timezone.now() - timedelta(days=days_ago),
        )
        for recipient_id in recipients:
            recipient, _ = MailRecipient.objects.get_or_create(recipient_id=recipient_id, recipient_type="character")
            mail.recipients.add(recipient)


class TestMails(MailTestCase):
    def test_should_sum_up_the_mails_with_one_hostile_in_one_case(self):
        (row,) = self.report_marker(markers.MAILS).rows

        self.assertEqual((row["key"], row["count"], row["types"]), (f"{self.prefix}0", 2, ["received", "sent"]))
        self.assertEqual(
            [(entry[1], entry[3]) for entry in row["entries"]], [("sent", "Re: Hello"), ("received", "Hello")]
        )
        # named with its Corporation and Alliance, as ISK and contracts
        self.assertEqual(row["corporation"]["standing"], "-10.0")

    def test_should_keep_an_undated_mail_in_the_case(self):
        self.add_mail(3, 13, HOSTILE_MEMBER, "Undated")
        snapshot.update()

        (row,) = self.report_marker(markers.MAILS).rows

        days = [(timezone.now() - timedelta(days=days_ago)).date().isoformat() for days_ago in (2, 1)]
        self.assertEqual((row["count"], row["first"], row["last"]), (3, *days))
        self.assertIn(("", "received", "0", "Undated"), row["entries"])

    def test_should_head_a_case_of_undated_mails_alone_without_a_day_button(self):
        MailMessage.objects.all().delete()
        self.add_mail(3, 13, HOSTILE_MEMBER, "Undated")
        snapshot.update()
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        (row,) = self.report_marker(markers.MAILS).rows
        self.assertEqual((row["first"], row["last"]), ("", ""))
        self.assertContains(response, f'data-eos-spy-network-kill-key="{self.prefix}0"')
        self.assertContains(response, f'data-eos-spy-network-kill-kind="{markers.MAILS}"', count=1)

    def test_should_open_a_new_case_for_a_mail_after_the_clear(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))
        self.client.post(
            reverse("eos_spy_network:finding_note"),
            {"kind": markers.MAILS, "main_id": self.main.character_id, "key": f"{self.prefix}0", "note": "Recruiting",
             "cleared": "1"},
        )
        self.assertEqual(sorted(FindingReview.objects.get(kind=markers.MAILS).items), [11, 12])
        self.assertNotIn(markers.MAILS, api.character_markers().get(self.main.character_id, []))

        self.add_mail(3, 13, HOSTILE_MEMBER, "Again", days_ago=0)
        snapshot.update()

        cases = {row["key"]: row for row in self.report_marker(markers.MAILS).rows}
        self.assertEqual((cases[f"{self.prefix}1"]["count"], cases[f"{self.prefix}1"]["cleared"]), (1, False))
        self.assertTrue(cases[f"{self.prefix}0"]["cleared"])

    def test_should_show_the_subjects_but_no_isk_and_no_ignore_button_on_the_corporation_page(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, '<td class="text-break">Re: Hello</td>', count=1)
        self.assertContains(response, f'data-eos-spy-network-kill-key="{self.prefix}0"')
        # the ISK row's button only: mails keep an ignored counterpart (user)
        self.assertContains(response, "data-eos-spy-network-ignore-id=", count=1)

    def test_should_list_the_mail_cases_in_their_settings_tab(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:settings") + "?tab=mails")

        self.assertEqual(response.context["tab"], "mails")
        self.assertContains(response, 'id="eos-spy-network-settings-mails"')
        self.assertEqual([row["key"] for row in response.context["mail_rows"]], [f"{self.prefix}0"])


class JoinTestCase(DealingTestCase):
    """Besides the donations: the main joined three Corporations within the year, as many as the marker needs."""

    def setUp(self):
        super().setUp()
        configure(corp_changes_per_year=3)
        for record_id, days_ago in ((1, 300), (2, 100), (3, 10)):
            self.add_join(record_id, days_ago)
        snapshot.update()
        self.prefix = f"{self.main.character_id}:"

    def add_join(self, record_id, days_ago):
        CorporationHistory.objects.create(
            character=self.audit, corporation_id=1000000 + record_id,
            corporation_name=eve_name(1000000 + record_id, "corporation"), record_id=record_id,
            start_date=timezone.now() - timedelta(days=days_ago),
        )

    def post(self, **fields):
        data = {"kind": markers.CORP_CHANGES, "main_id": self.main.character_id, "key": f"{self.prefix}0"}
        return self.client.post(reverse("eos_spy_network:finding_note"), {**data, **fields})


class TestCorporationChanges(JoinTestCase):
    def test_should_show_one_case_per_character_with_each_join(self):
        (row,) = self.report_marker(markers.CORP_CHANGES).rows

        self.assertEqual((row["key"], row["count"]), (f"{self.prefix}0", 3))
        self.assertEqual([entry[1] for entry in row["entries"]], ["Name 1000003", "Name 1000002", "Name 1000001"])
        self.assertEqual(row["last"], (timezone.now() - timedelta(days=10)).date().isoformat())

    def test_should_reopen_the_character_with_every_join_after_a_new_one(self):
        # the user's rule (2026-11-27): the number is the finding, so the new case counts the whole year
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))
        self.post(note="Moved for a war", cleared="1")
        self.assertEqual(sorted(FindingReview.objects.get(kind=markers.CORP_CHANGES).items), [1, 2, 3])
        self.assertIsNone(self.report_marker(markers.CORP_CHANGES))
        self.assertNotIn(markers.CORP_CHANGES, api.character_markers().get(self.main.character_id, []))

        self.add_join(4, 1)
        snapshot.update()

        marker = self.report_marker(markers.CORP_CHANGES)
        cases = {row["key"]: row for row in marker.rows}
        self.assertEqual((cases[f"{self.prefix}1"]["count"], cases[f"{self.prefix}1"]["cleared"]), (4, False))
        self.assertEqual((cases[f"{self.prefix}0"]["count"], cases[f"{self.prefix}0"]["cleared"]), (3, True))
        self.assertEqual(marker.count, 4)

    def test_should_stay_cleared_while_no_join_comes(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))
        self.post(note="Moved for a war", cleared="1")
        snapshot.update()

        self.assertIsNone(self.report_marker(markers.CORP_CHANGES))

    def test_should_show_the_case_with_its_tick_and_day_row_on_the_corporation_page(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, f'data-eos-spy-network-kill-key="{self.prefix}0"')
        self.assertContains(response, f'data-eos-spy-network-kill-kind="{markers.CORP_CHANGES}"', count=2)
        self.assertContains(response, "<td>Name 1000003</td>", count=1)

    def test_should_list_the_case_in_its_settings_tab_and_name_it_in_the_log(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))
        self.post(cleared="1")

        response = self.client.get(reverse("eos_spy_network:settings") + "?tab=corp_changes")

        self.assertEqual(response.context["tab"], "corp_changes")
        self.assertContains(response, 'id="eos-spy-network-settings-corp_changes"')
        self.assertEqual([row["cleared"] for row in response.context["join_rows"]], [True])
        self.assertContains(self.client.get(reverse("eos_spy_network:log")), f"{self.main.character_name}: 3")


class MembershipTestCase(DealingTestCase):
    """Besides the donations: an alt in the hostile Corporation since 100 days, by Auth and by its history."""

    ALT = 5001

    def setUp(self):
        super().setUp()
        self.alt = self.add_alt(self.ALT, corporation_id=HOSTILE_CORP, alliance_id=None)
        self.alt_audit = CharacterAudit.objects.create(character=self.alt)
        self.add_record(self.alt_audit, 1, HOSTILE_CORP, 100)
        snapshot.update()
        self.prefix = f"{HOSTILE_CORP}:"

    @staticmethod
    def add_record(audit, record_id, corporation_id, days_ago):
        CorporationHistory.objects.create(
            character=audit, corporation_id=corporation_id, corporation_name=eve_name(corporation_id, "corporation"),
            record_id=record_id, start_date=timezone.now() - timedelta(days=days_ago),
        )

    def move(self, character, corporation_id):
        character.corporation_id = corporation_id
        character.save()

    def clear(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))
        self.client.post(
            reverse("eos_spy_network:finding_note"),
            {"kind": markers.MEMBERSHIP, "main_id": self.main.character_id, "key": f"{self.prefix}0",
             "note": "Spy for us", "cleared": "1"},
        )

    def cases(self):
        return {row["key"]: row for row in self.report_marker(markers.MEMBERSHIP).rows}


class TestMembership(MembershipTestCase):
    def test_should_show_one_case_per_group_with_its_record(self):
        (row,) = self.report_marker(markers.MEMBERSHIP).rows

        self.assertEqual((row["key"], row["group"], row["count"]), (f"{self.prefix}0", "Bad Corp", 1))
        joined = (timezone.now() - timedelta(days=100)).date().isoformat()
        self.assertEqual(row["items"][0][:2], [f"{self.ALT}:1", joined])
        self.assertEqual(row["named_characters"], [(self.ALT, f"Char {self.ALT}")])

    def test_should_take_the_membership_from_auth_without_a_history(self):
        CorporationHistory.objects.all().delete()
        snapshot.update()

        (row,) = self.report_marker(markers.MEMBERSHIP).rows

        self.assertEqual((row["items"][0][0], row["last"]), (f"{self.ALT}:auth", ""))

    def test_should_drop_the_marker_once_the_group_is_cleared(self):
        self.clear()

        self.assertEqual(FindingReview.objects.get(kind=markers.MEMBERSHIP).items, [f"{self.ALT}:1"])
        self.assertIsNone(self.report_marker(markers.MEMBERSHIP))
        self.assertNotIn(self.ALT, api.character_markers())

    def test_should_stay_cleared_when_the_character_leaves(self):
        self.clear()
        self.add_record(self.alt_audit, 2, 2001, 10)
        self.move(self.alt, 2001)
        snapshot.update()

        self.assertIsNone(self.report_marker(markers.MEMBERSHIP))

    def test_should_open_a_new_case_when_the_character_joins_again(self):
        self.clear()
        self.add_record(self.alt_audit, 2, 2001, 10)
        self.add_record(self.alt_audit, 3, HOSTILE_CORP, 1)
        snapshot.update()

        cases = self.cases()

        self.assertEqual([item[0] for item in cases[f"{self.prefix}1"]["items"]], [f"{self.ALT}:3"])
        self.assertTrue(cases[f"{self.prefix}0"]["cleared"])

    def test_should_open_a_new_case_for_a_character_newly_added_in_the_group(self):
        self.clear()
        self.add_alt(5002, corporation_id=HOSTILE_CORP, alliance_id=None)
        snapshot.update()

        cases = self.cases()

        self.assertEqual(cases[f"{self.prefix}1"]["named_characters"], [(5002, "Char 5002")])
        self.assertFalse(cases[f"{self.prefix}1"]["cleared"])
        self.assertEqual(self.report_marker(markers.MEMBERSHIP).count, 1)

    def test_should_show_the_case_on_the_corporation_page_and_in_its_settings_tab(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, f'data-eos-spy-network-kill-key="{self.prefix}0"')
        self.assertContains(response, f'data-eos-spy-network-kill-kind="{markers.MEMBERSHIP}"', count=2)
        response = self.client.get(reverse("eos_spy_network:settings") + "?tab=membership")
        self.assertContains(response, 'id="eos-spy-network-settings-membership"')
        self.assertEqual([row["key"] for row in response.context["membership_rows"]], [f"{self.prefix}0"])

    def test_should_name_the_group_in_the_log(self):
        self.clear()
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

        self.assertContains(self.client.get(reverse("eos_spy_network:log")), "Bad Corp")


class TestSettingsTabAndLog(DealingTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

    def test_should_list_every_case_in_its_tab(self):
        self.review()

        response = self.client.get(reverse("eos_spy_network:settings") + "?tab=wallet")

        self.assertEqual(response.context["tab"], "wallet")
        self.assertContains(response, 'id="eos-spy-network-settings-wallet"')
        self.assertContains(response, 'id="eos-spy-network-settings-contracts"')
        self.assertContains(response, f'data-eos-spy-network-kill-key="{self.prefix}0"')
        self.assertEqual([row["cleared"] for row in response.context["wallet_rows"]], [True])

    def test_should_name_the_case_in_the_log(self):
        self.client.post(
            reverse("eos_spy_network:finding_note"),
            {"kind": markers.WALLET, "main_id": self.main.character_id, "key": f"{self.prefix}0", "cleared": "1"},
        )

        response = self.client.get(reverse("eos_spy_network:log"))

        self.assertContains(response, f"{self.main.character_name} – Bad Corp")


class OwnerTestCase(MarkerTestCase):
    """An alt of the main that its earlier owner (``seller``) held under another owner hash."""

    ALT = 5001

    def setUp(self):
        super().setUp()
        self.alt = self.add_alt(self.ALT)
        self.seller = make_user("seller")
        self.record = OwnershipRecord.objects.create(user=self.seller, character=self.alt, owner_hash="seller-hash")
        snapshot.update()
        self.prefix = f"{self.ALT}:"

    def report(self):
        return snapshot.Report(snapshot.current(), (), {}, snapshot.finding_reviews(ALLIANCE_ID))

    def report_marker(self):
        suspects = self.report().tile(2001).suspects
        suspect = next((suspect for suspect in suspects if suspect.user_id == self.user.pk), None)
        return suspect.markers.get(markers.OWNER_CHANGES) if suspect else None

    def cases(self):
        return {row["key"]: row for row in self.report_marker().rows}

    def post(self, **fields):
        data = {"kind": markers.OWNER_CHANGES, "main_id": self.main.character_id, "key": f"{self.prefix}0"}
        return self.client.post(reverse("eos_spy_network:finding_note"), {**data, **fields})

    def clear(self):
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))
        self.post(note="Bought from a friend", cleared="1")


class TestOwnerChanges(OwnerTestCase):
    def test_should_show_a_character_with_an_earlier_owner_hash(self):
        marker = self.report_marker()
        (row,) = marker.rows

        self.assertEqual((row["key"], row["count"], marker.count), (f"{self.prefix}0", 1, 1))
        self.assertEqual(row["items"], [[self.record.pk, timezone.now().date().isoformat(), "seller main"]])
        self.assertEqual(row["named_characters"], [(self.ALT, f"Char {self.ALT}")])
        self.assertEqual(marker.character_ids, {self.ALT})
        self.assertEqual(marker.details, {f"Char {self.ALT}: seller main"})

    def test_should_not_show_a_character_that_only_moved_between_accounts_of_its_owner(self):
        # the same hash under another Auth account: the same player, not a sale
        OwnershipRecord.objects.filter(pk=self.record.pk).update(owner_hash=f"hash-{self.ALT}")
        snapshot.update()

        self.assertIsNone(self.report_marker())

    def test_should_name_the_user_of_an_earlier_owner_without_a_main(self):
        profile = self.seller.profile
        profile.main_character = None
        profile.save()
        snapshot.update()

        (row,) = self.report_marker().rows

        self.assertEqual(row["items"][0][2], "seller")

    def test_should_drop_the_marker_once_the_character_is_cleared(self):
        self.clear()

        self.assertEqual(FindingReview.objects.get(kind=markers.OWNER_CHANGES).items, [self.record.pk])
        self.assertIsNone(self.report_marker())
        self.assertNotIn(self.ALT, api.character_markers())
        (cleared,) = self.report().tile(2001).cleared
        self.assertEqual(
            [(row["finding"], row["note"]) for row in cleared["rows"]], [("seller main", "Bought from a friend")]
        )

    def test_should_stay_cleared_while_no_further_owner_comes(self):
        self.clear()
        snapshot.update()

        self.assertIsNone(self.report_marker())

    def test_should_open_a_new_case_for_a_further_earlier_owner(self):
        self.clear()
        OwnershipRecord.objects.create(user=make_user("seller2"), character=self.alt, owner_hash="seller2-hash")
        snapshot.update()

        cases = self.cases()

        self.assertEqual((cases[f"{self.prefix}1"]["count"], cases[f"{self.prefix}1"]["cleared"]), (1, False))
        self.assertEqual((cases[f"{self.prefix}0"]["count"], cases[f"{self.prefix}0"]["cleared"]), (1, True))
        self.assertEqual(self.report_marker().count, 1)
        self.assertIn(markers.OWNER_CHANGES, api.character_markers()[self.ALT])

    def test_should_show_the_case_on_the_corporation_page_and_in_its_settings_tab(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))

        response = self.client.get(reverse("eos_spy_network:corporation", args=[2001]))

        self.assertContains(response, f'data-eos-spy-network-kill-key="{self.prefix}0"')
        self.assertContains(response, f'data-eos-spy-network-kill-kind="{markers.OWNER_CHANGES}"', count=2)
        response = self.client.get(reverse("eos_spy_network:settings") + "?tab=owner_changes")
        self.assertEqual(response.context["tab"], "owner_changes")
        self.assertContains(response, 'id="eos-spy-network-settings-owner_changes"')
        self.assertEqual([row["key"] for row in response.context["owner_rows"]], [f"{self.prefix}0"])

    def test_should_name_the_case_in_the_log(self):
        self.client.force_login(make_user("admin", MANAGE_SETTINGS, VIEW_SUSPECTS))
        self.post(cleared="1")

        self.assertContains(self.client.get(reverse("eos_spy_network:log")), f"Char {self.ALT}: 1")
