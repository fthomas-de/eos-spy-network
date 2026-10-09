from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls
from .permissions import has_app_access


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

        return MenuItemHook.render(self, request)


@hooks.register("menu_item_hook")
def register_menu():
    return SpyNetworkMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "eos_spy_network", r"^eos_spy_network/")
