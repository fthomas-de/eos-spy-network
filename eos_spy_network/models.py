from decimal import Decimal

from solo.models import SingletonModel

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from allianceauth.eveonline.models import EveAllianceInfo


class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("view_suspects", "Can view the suspects and the hostile list"),
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

    class Meta:
        default_permissions = ()
        verbose_name = _("Configuration")

    def __str__(self):
        return str(_("Configuration"))


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
