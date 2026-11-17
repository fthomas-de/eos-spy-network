from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls
from .permissions import VIEW_SUSPECTS, has_app_access, own_corporation_id
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
        if request.user.has_perm(VIEW_SUSPECTS):
            self.count = open_mains()
        else:
            corporation_id = own_corporation_id(request.user)
            self.count = None if corporation_id is None else open_mains(corporation_id)
        return MenuItemHook.render(self, request)


@hooks.register("menu_item_hook")
def register_menu():
    return SpyNetworkMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "eos_spy_network", r"^eos_spy_network/")
