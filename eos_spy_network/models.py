from datetime import timedelta
from decimal import Decimal

from solo.models import SingletonModel

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from allianceauth.eveonline.models import EveAllianceInfo


def default_ignored_ref_types() -> list[str]:
    # buying from or selling to a hostile on the market is anonymous: nobody picks the other side
    return ["market_transaction"]


def default_note_presets() -> list[str]:
    # the user's two everyday reasons a blue died to an own character
    return ["bomb", "sb ratting"]


def default_capital_ship_groups() -> list[str]:
    # group names, not type IDs: a new capital hull of a group counts without a change here; Freighters
    # and Jump Freighters are left out (user) but can be picked
    return [
        "Dreadnought",
        "Lancer Dreadnought",
        "Carrier",
        "Command Carrier",
        "Force Auxiliary",
        "Supercarrier",
        "Titan",
        "Capital Industrial Ship",
    ]


class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("view_suspects", "Can view the suspects per Corporation"),
            ("manage_settings", "Can change the Alliance, the contact sources and the thresholds"),
            ("view_own_corporation", "Can view the suspects and evidence of their main's own Corporation"),
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
    blue_from = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal("5"),
        validators=[MinValueValidator(Decimal("-10")), MaxValueValidator(Decimal("10"))],
        verbose_name=_("Blue from standing"),
        help_text=_(
            "A kill counts as a blue kill when the victim is in the Alliance, or when the victim, its "
            "Corporation or Alliance has at least this standing with the Alliance. Only the Alliance's own "
            "contacts count, not those of its Corporations."
        ),
    )
    # million ISK, as killtracker's own trackers take their minimum value
    min_kill_value = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Minimum kill value in million ISK"),
        help_text=_(
            "A blue kill worth less, by zKillboard's value, does not count - a capsule or a shuttle is no "
            "awox worth a look. A kill without a known value counts. 0 counts every kill."
        ),
    )
    # names, not type IDs: a BlueKill keeps only the name of the victim's ship
    ignored_ships = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Ignored ships"),
        help_text=_("A blue kill whose victim flew one of these does not count."),
    )
    capital_ship_groups = models.JSONField(
        default=default_capital_ship_groups,
        blank=True,
        verbose_name=_("Capital ship groups"),
        help_text=_("An open public contract offering a ship of these groups marks its issuer."),
    )
    note_presets = models.JSONField(
        default=default_note_presets,
        blank=True,
        verbose_name=_("Note buttons"),
        help_text=_(
            "A button each in the note popup of a blue kill: a click enters the text, ticks Cleared and saves. "
            "Type a new text and press Enter."
        ),
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
    network_neutral = models.BooleanField(
        default=False,
        verbose_name=_("Network: neutral partners too"),
        help_text=_(
            "Off, the Network shows only partners that are hostile themselves or through their Corporation or "
            "Alliance. On, the neutral ones too; a blue one stays out unless something in its chain is hostile."
        ),
    )
    network_blue_above = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("-10")), MaxValueValidator(Decimal("10"))],
        verbose_name=_("Network: blue above standing"),
        help_text=_(
            "With neutral partners on: a partner, its Corporation or its Alliance with a standing above this "
            "value at a ticked source is blue and leaves the Network."
        ),
    )
    # EVE IDs: a character is ignored as a source of findings, its alts and main stay checked
    ignored_contact_characters = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Ignored characters"),
        help_text=_("The contacts of these characters are not checked for friendly hostiles."),
    )
    ignored_network_characters = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Ignored characters"),
        help_text=_(
            "The payments and contracts of these characters do not count for the Network. A partner shared with "
            "the account's other characters still counts."
        ),
    )
    # the switched-off ones, not the switched-on: a marker added in a later version starts on
    disabled_markers = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Markers switched off"),
        help_text=_("Still calculated, but left out of the Markers pages until switched on again."),
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


# a short remark, not a case file - as the GM transaction notes of eos-tax
KILL_NOTE_LENGTH = 160


class BlueKill(models.Model):
    """A blue kill as found in killtracker, kept after killtracker deletes the killmail.

    killtracker purges its killmails after a few days; the marker would forget
    a kill with them. Each calculation copies what it finds here, so a kill
    stays as long as one calculation ran before the purge. Awox or blue is
    judged once, when copied: a standing changed later does not undo a kill
    of a friend.
    """

    AWOX = "awox"
    BLUE = "blue"

    # the configured Alliance the kill was judged for: another Alliance has other friends
    alliance_id = models.PositiveBigIntegerField()
    killmail_id = models.PositiveBigIntegerField()
    # the own character among the attackers
    character_id = models.PositiveBigIntegerField()
    time = models.DateTimeField()
    victim_id = models.PositiveBigIntegerField(null=True)
    victim = models.CharField(max_length=254, blank=True)
    victim_corporation_id = models.PositiveBigIntegerField(null=True)
    victim_corporation = models.CharField(max_length=254, blank=True)
    victim_alliance_id = models.PositiveBigIntegerField(null=True)
    victim_alliance = models.CharField(max_length=254, blank=True)
    ship = models.CharField(max_length=254, blank=True)
    # zKillboard's value in ISK, as killtracker keeps it; none when zKillboard sent none
    value = models.FloatField(null=True)
    reason = models.CharField(max_length=8)
    # the blue's standing at the time it was copied; none for an awox
    standing = models.DecimalField(max_digits=3, decimal_places=1, null=True)
    # the review lives here: a later copy updates the names only and leaves it alone
    cleared = models.BooleanField(default=False)
    note = models.CharField(max_length=KILL_NOTE_LENGTH, blank=True)
    reviewed_at = models.DateTimeField(null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["alliance_id", "character_id", "killmail_id"], name="eos_spy_network_unique_blue_kill"
            )
        ]

    def __str__(self):
        return f"Killmail {self.killmail_id} by {self.character_id}"


class FindingReview(models.Model):
    """The note and the cleared tick of one finding of a marker.

    Kept apart from the snapshot, which each run overwrites. Applied when a
    page is read, so a tick takes effect at once. A finding belongs to the
    main (the user's rule): an alt that shows the same finding later is
    cleared with it.
    """

    # the configured Alliance it was reviewed for: another Alliance has other hostiles
    alliance_id = models.PositiveBigIntegerField()
    kind = models.CharField(max_length=32)
    main_id = models.PositiveBigIntegerField()
    # what tells the main's findings of one marker apart, e.g. "<contact ID>:<standing>" for the contacts
    key = models.CharField(max_length=64)
    cleared = models.BooleanField(default=False)
    note = models.CharField(max_length=KILL_NOTE_LENGTH, blank=True)
    reviewed_at = models.DateTimeField(null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["alliance_id", "kind", "main_id", "key"], name="eos_spy_network_unique_finding_review"
            )
        ]

    def __str__(self):
        return f"{self.kind} {self.key} of {self.main_id}"


class ReviewLog(models.Model):
    """One save of a note and cleared tick, of a blue kill or another finding.

    The review rows keep only the latest state; this keeps every change, so a
    reader can tell who cleared what and what the note said before.
    """

    alliance_id = models.PositiveBigIntegerField()
    # the marker: blue_kills or the kind of a FindingReview
    kind = models.CharField(max_length=32)
    # the main of a finding; for a blue kill the character it was saved for, its main looked up when shown
    character_id = models.PositiveBigIntegerField()
    # the killmail ID for a blue kill, the FindingReview key otherwise
    key = models.CharField(max_length=64)
    cleared = models.BooleanField()
    note = models.CharField(max_length=KILL_NOTE_LENGTH, blank=True)
    # none for the first save and for the entries copied from the reviews made before the log
    previous_cleared = models.BooleanField(null=True)
    previous_note = models.CharField(max_length=KILL_NOTE_LENGTH, blank=True)
    changed_at = models.DateTimeField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        default_permissions = ()

    def __str__(self):
        return f"{self.kind} {self.key} of {self.character_id} at {self.changed_at}"


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


class CapitalContract(models.Model):
    """An open public contract of an Alliance Corporation, found by the daily sweep of the public contracts.

    A row stays only while the contract is listed and not expired; its items never change, so they are
    fetched once.
    """

    contract_id = models.PositiveBigIntegerField(primary_key=True)
    issuer_id = models.PositiveBigIntegerField(db_index=True)
    issuer_corporation_id = models.PositiveBigIntegerField()
    contract_type = models.CharField(max_length=16)
    title = models.CharField(max_length=254, blank=True)
    price = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    buyout = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    date_issued = models.DateTimeField()
    date_expired = models.DateTimeField()
    # region and station name; a structure has no public name, it shows as its ID
    location = models.CharField(max_length=254, blank=True)

    class Meta:
        default_permissions = ()

    def __str__(self):
        return f"Contract {self.contract_id} of {self.issuer_id}"


class CapitalContractItem(models.Model):
    contract = models.ForeignKey(CapitalContract, on_delete=models.CASCADE, related_name="items")
    # no database constraint: an SDE that lacks a new type must not stop the sweep, the row only never matches
    type = models.ForeignKey("eve_sde.ItemType", on_delete=models.DO_NOTHING, db_constraint=False, related_name="+")
    quantity = models.PositiveIntegerField()
    is_included = models.BooleanField()

    class Meta:
        default_permissions = ()


class SweepStats(models.Model):
    """The counts of the last contract sweep, for the Statistics page; one row, overwritten each run.

    Not a solo model, as Snapshot: SOLO_CACHE would keep a stale copy in the cache.
    """

    finished_at = models.DateTimeField()
    seconds = models.FloatField()
    regions = models.PositiveIntegerField()
    regions_failed = models.PositiveIntegerField()
    # every open public contract ESI listed, of anyone
    public_contracts = models.PositiveIntegerField()
    # those of the Alliance's Corporations the sweep keeps
    contracts = models.PositiveIntegerField()
    issuers = models.PositiveIntegerField()
    corporations = models.PositiveIntegerField()
    added = models.PositiveIntegerField()
    items_failed = models.PositiveIntegerField()
    removed = models.PositiveIntegerField()
    # region name -> contracts of the Alliance; Corporation ID (a string, as JSON keys are) -> contracts
    per_region = models.JSONField(default=dict)
    per_corporation = models.JSONField(default=dict)

    class Meta:
        default_permissions = ()

    def __str__(self):
        return f"Sweep {self.finished_at:%Y-%m-%d %H:%M}"
