from django import forms
from django.apps import apps
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from allianceauth.eveonline.models import EveAllianceInfo

from .markers import DESCRIPTIONS, KINDS, LABELS
from .models import BlueKill, SpyConfiguration
from .network import PAYMENT_REF_TYPES


def ref_type_choices(stored=()) -> list[tuple[str, str]]:
    """Every wallet entry type corptools holds, the payment types and whatever is stored already."""
    ref_types = set(PAYMENT_REF_TYPES) | set(stored or ())
    if apps.is_installed("corptools"):
        from corptools.models import CharacterWalletJournalEntry

        # ref_type carries an index: the distinct values come from it, not from the whole journal
        ref_types |= set(CharacterWalletJournalEntry.objects.values_list("ref_type", flat=True).distinct())
    return [(ref_type, ref_type.replace("_", " ")) for ref_type in sorted(ref_types)]


def ship_choices(stored=()) -> list[tuple[str, str]]:
    """Every type killtracker offers as a victim's ship, the ships of the stored blue kills and whatever
    is stored already."""
    ships = set(stored or ()) | set(BlueKill.objects.values_list("ship", flat=True).distinct())
    if apps.is_installed("killtracker"):
        from eveuniverse.models import EveType

        try:
            from killtracker.models.trackers import _require_victim_ship_types_query
        except ImportError:  # a private name of killtracker: without it the stored names still serve
            pass
        else:
            ships |= set(EveType.objects.filter(_require_victim_ship_types_query()).values_list("name", flat=True))
    # killtracker stores a killmail before it resolves the names: an empty ship is a fresh one
    ships.discard("")
    return [(ship, ship) for ship in sorted(ships)]


class SpyConfigurationForm(forms.ModelForm):
    alliance = forms.ModelChoiceField(
        label=pgettext_lazy("EVE jargon", "Alliance"),
        queryset=EveAllianceInfo.objects.order_by("alliance_name"),
        required=False,
        help_text=SpyConfiguration._meta.get_field("alliance").help_text,
        widget=forms.Select(attrs={"data-eos-spy-network-search": ""}),
    )
    ignored_ref_types = forms.MultipleChoiceField(
        label=SpyConfiguration._meta.get_field("ignored_ref_types").verbose_name,
        required=False,
        help_text=SpyConfiguration._meta.get_field("ignored_ref_types").help_text,
        widget=forms.SelectMultiple(attrs={"data-eos-spy-network-search": ""}),
    )
    ignored_ships = forms.MultipleChoiceField(
        label=SpyConfiguration._meta.get_field("ignored_ships").verbose_name,
        required=False,
        help_text=SpyConfiguration._meta.get_field("ignored_ships").help_text,
        widget=forms.SelectMultiple(attrs={"data-eos-spy-network-search": ""}),
    )
    # the switched-on markers; stored the other way round, as disabled_markers
    markers = forms.MultipleChoiceField(
        label=_("Markers"),
        required=False,
        choices=[(kind, LABELS[kind]) for kind in KINDS],
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = SpyConfiguration
        fields = [
            "alliance",
            "hostile_below",
            "blue_from",
            "min_kill_value",
            "ignored_ships",
            "corp_changes_per_year",
            "lookback_days",
            "ignored_ref_types",
        ]
        widgets = {
            "hostile_below": forms.NumberInput(attrs={"step": "0.1", "min": "-10", "max": "10"}),
            "blue_from": forms.NumberInput(attrs={"step": "0.1", "min": "-10", "max": "10"}),
            "corp_changes_per_year": forms.NumberInput(attrs={"min": "2", "max": "50"}),
            "lookback_days": forms.NumberInput(attrs={"min": "0", "max": "3650"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ignored_ref_types"].choices = ref_type_choices(self.instance.ignored_ref_types)
        self.fields["ignored_ships"].choices = ship_choices(self.instance.ignored_ships)
        disabled = self.instance.disabled_markers or ()
        self.fields["markers"].initial = [kind for kind in KINDS if kind not in disabled]

    def marker_switches(self) -> list[tuple]:
        """Each marker's checkbox with its description, for the switches of the Markers tab."""
        return [(option, DESCRIPTIONS[option.data["value"]]) for option in self["markers"]]

    def save(self, commit=True):
        self.instance.disabled_markers = [kind for kind in KINDS if kind not in self.cleaned_data["markers"]]
        return super().save(commit)
