from django.apps import AppConfig

from eos_spy_network import __version__


class EosSpyNetworkConfig(AppConfig):
    name = "eos_spy_network"
    label = "eos_spy_network"
    verbose_name = f"EOS Spy Network v{__version__}"
    default_auto_field = "django.db.models.BigAutoField"
