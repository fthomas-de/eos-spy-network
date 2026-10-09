from unittest.mock import patch

from kombu.exceptions import OperationalError

from django.urls import reverse

from eos_spy_network import progress
from eos_spy_network.tasks import update_snapshot

from .base import SpyTestCase, configure, make_corporation, make_user

VIEW_SUSPECTS = "eos_spy_network.view_suspects"


class TestTask(SpyTestCase):
    def setUp(self):
        super().setUp()
        configure()
        make_corporation(2001)
        make_user("member")

    def test_should_report_every_step_in_order_and_clear_the_bar(self):
        with patch("eos_spy_network.progress.step", wraps=progress.step) as step:
            update_snapshot()

        steps = [call.args[0] for call in step.call_args_list]
        self.assertEqual(steps[0], "hostiles")
        self.assertEqual(steps[-3:], ["connections", "affiliations", "saving"])
        self.assertEqual(steps, sorted(steps, key=progress.ORDER.index))
        self.assertIsNone(progress.current())

    def test_should_clear_the_bar_when_the_calculation_fails(self):
        progress.step("wallet")

        with patch("eos_spy_network.snapshot.update", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                update_snapshot()

        self.assertIsNone(progress.current())


class TestState(SpyTestCase):
    def test_should_grow_with_the_steps(self):
        progress.step("hostiles")
        first = progress.current()["percent"]
        progress.step("saving")

        self.assertLess(first, progress.current()["percent"])
        self.assertLess(progress.current()["percent"], 100)

    def test_should_not_overwrite_a_running_step_with_queued(self):
        progress.step("wallet")
        progress.queued()

        self.assertEqual(progress.current()["step"], "wallet")


class TestPages(SpyTestCase):
    def setUp(self):
        super().setUp()
        configure()
        make_corporation(2001)
        self.client.force_login(make_user("viewer", VIEW_SUSPECTS))

    def test_should_show_the_bar_instead_of_the_button_after_the_click(self):
        self.client.post(reverse("eos_spy_network:rebuild"), {"next": reverse("eos_spy_network:corporations")})

        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertContains(response, "data-eos-spy-network-progress")
        self.assertNotContains(response, f'action="{reverse("eos_spy_network:rebuild")}"')

    def test_should_show_the_button_while_nothing_runs(self):
        response = self.client.get(reverse("eos_spy_network:corporations"))

        self.assertNotContains(response, "data-eos-spy-network-progress=")
        self.assertContains(response, f'action="{reverse("eos_spy_network:rebuild")}"')

    def test_should_drop_the_bar_when_the_broker_is_down(self):
        self.update_snapshot.delay.side_effect = OperationalError("down")

        self.client.post(reverse("eos_spy_network:rebuild"))

        self.assertIsNone(progress.current())

    def test_should_answer_the_poll_with_the_running_step(self):
        progress.step("mails")

        state = self.client.get(reverse("eos_spy_network:rebuild_progress")).json()

        self.assertTrue(state["running"])
        self.assertEqual(state["step"], "mails")
        self.assertEqual(state["label"], "Checking mails")

    def test_should_answer_the_poll_when_done(self):
        state = self.client.get(reverse("eos_spy_network:rebuild_progress")).json()

        self.assertEqual(state, {"running": False})

    def test_should_keep_the_poll_from_users_without_permission(self):
        self.client.force_login(make_user("nobody"))

        response = self.client.get(reverse("eos_spy_network:rebuild_progress"))

        self.assertEqual(response.status_code, 302)
