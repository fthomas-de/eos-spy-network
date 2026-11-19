"""The menu badge: the mains with open markers, for those who may see them."""

from django.test import RequestFactory

from eos_spy_network.auth_hooks import SpyNetworkMenuItem

from .base import configure, make_user
from .test_views import MANAGE_SETTINGS, VIEW_SUSPECTS, SuspectPageTestCase


class TestMenuBadge(SuspectPageTestCase):
    """The suspect is marked by Hostile membership only."""

    @staticmethod
    def count(user):
        request = RequestFactory().get("/")
        request.user = user
        item = SpyNetworkMenuItem()
        item.render(request)
        return item.count

    def test_should_count_the_mains_with_markers(self):
        self.assertEqual(self.count(make_user("viewer", VIEW_SUSPECTS)), 1)

    def test_should_leave_out_switched_off_markers(self):
        configure(disabled_markers=["membership"])

        self.assertEqual(self.count(make_user("viewer", VIEW_SUSPECTS)), 0)

    def test_should_show_no_count_without_view_suspects(self):
        self.assertIsNone(self.count(make_user("admin", MANAGE_SETTINGS)))

    def test_should_not_keep_the_count_of_the_previous_user(self):
        item = SpyNetworkMenuItem()
        request = RequestFactory().get("/")
        request.user = make_user("viewer", VIEW_SUSPECTS)
        item.render(request)
        request.user = make_user("admin", MANAGE_SETTINGS)

        item.render(request)

        self.assertIsNone(item.count)
