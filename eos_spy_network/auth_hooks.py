from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls
from .permissions import VIEW_SUSPECTS, has_app_access
from .views import open_mains


class SpyNetworkMenuItem(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("Spy Network"),
            "fas fa-user-secret",
            "eos_spy_network:index",
            navactive=["eos_spy_network:"],
        )

    def render(self, request):
        if not has_app_access(request.user):
            return ""

        # one hook object serves every user: reset the count of the previous one
        self.count = open_mains() if request.user.has_perm(VIEW_SUSPECTS) else None
        return MenuItemHook.render(self, request)


@hooks.register("menu_item_hook")
def register_menu():
    return SpyNetworkMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "eos_spy_network", r"^eos_spy_network/")
