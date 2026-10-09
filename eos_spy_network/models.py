from datetime import timedelta
from decimal import Decimal

from solo.models import SingletonModel

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from allianceauth.eveonline.models import EveAllianceInfo


def default_ignored_ref_types() -> list[str]:
    # buying from or selling to a hostile on the market is anonymous: nobody picks the other side
    return ["market_transaction"]


class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("view_suspects", "Can view the suspects per Corporation"),
            ("view_evidence", "Can view the evidence: mail headers and subjects, wallet and contracts"),
            ("manage_settings", "Can change the Alliance, the contact sources and the thresholds"),
        )


class SpyConfiguration(SingletonModel):
    """App wide settings, maintained on the settings page."""

    alliance = models.ForeignKey(
        EveAllianceInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=pgettext_lazy("EVE jargon", "Alliance"),
        help_text=_("The Alliance whose members are checked."),
    )
    hostile_below = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("-10")), MaxValueValidator(Decimal("10"))],
        verbose_name=_("Hostile below standing"),
        help_text=_("A contact of a ticked source counts as hostile when its standing is below this value."),
    )
    corp_changes_per_year = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(2), MaxValueValidator(50)],
        verbose_name=_("Corporation changes per year"),
        help_text=_("A character that joined this many Corporations within the last 365 days gets a marker."),
    )

    lookback_days = models.PositiveSmallIntegerField(
        default=365,
        validators=[MaxValueValidator(3650)],
        verbose_name=_("Time frame in days"),
        help_text=_(
            "Only the last this many days count: wallet, contracts, mails, the network's payments and former "
            "Corporations. Standings change - a hostile today may have been a friend back then. 0 takes everything."
        ),
    )
    ignored_ref_types = models.JSONField(
        default=default_ignored_ref_types,
        blank=True,
        verbose_name=_("Ignored wallet entry types"),
        help_text=_("Wallet journal entries of these types count neither as ISK with hostiles nor as a payment."),
    )

    class Meta:
        default_permissions = ()
        verbose_name = _("Configuration")

    def __str__(self):
        return str(_("Configuration"))

    def since(self):
        """The start of the time frame; None takes everything."""
        if not self.lookback_days:
            return None
        return timezone.now() - timedelta(days=self.lookback_days)


class Snapshot(models.Model):
    """The last result of the calculation; one row, overwritten each run.

    Not a solo model on purpose: SOLO_CACHE would put the whole result into the
    cache on every read.
    """

    built_at = models.DateTimeField()
    data = models.JSONField(default=dict)

    class Meta:
        default_permissions = ()

    def __str__(self):
        return f"Snapshot {self.built_at:%Y-%m-%d %H:%M}"


class ContactSource(models.Model):
    """The Alliance or one of its Corporations whose aa-contacts contacts make up the hostile list.

    One row per ticked entry of the settings page; unticking deletes the row.
    The contacts themselves stay in aa-contacts.
    """

    ALLIANCE = "alliance"
    CORPORATION = "corporation"
    KIND_CHOICES = (
        (ALLIANCE, pgettext_lazy("EVE jargon", "Alliance")),
        (CORPORATION, pgettext_lazy("EVE jargon", "Corporation")),
    )

    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    entity_id = models.PositiveBigIntegerField()
    # kept so a Corporation that left the Alliance still has a name in the table
    name = models.CharField(max_length=254, blank=True)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["kind", "entity_id"], name="eos_spy_network_unique_source")]

    def __str__(self):
        return f"{self.get_kind_display()} {self.name or self.entity_id}"
