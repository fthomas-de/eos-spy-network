from django import forms
from django.apps import apps
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from allianceauth.eveonline.models import EveAllianceInfo

from .markers import CONTACTS, DESCRIPTIONS, KINDS, LABELS, roster
from .models import KILL_NOTE_LENGTH, BlueKill, SpyConfiguration
from .network import PAYMENT_REF_TYPES
from .snapshot import Report, category_label, current


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


# eve_sde's ItemCategory of ships
SHIP_CATEGORY = 6


def capital_group_choices(stored=()) -> list[tuple[str, str]]:
    """Every ship group eve_sde holds and whatever is stored already."""
    groups = set(stored or ())
    if apps.is_installed("eve_sde"):
        from eve_sde.models import ItemGroup

        groups |= set(ItemGroup.objects.filter(category_id=SHIP_CATEGORY, published=True).values_list("name", flat=True))
    return [(group, group) for group in sorted(groups)]


def marked_characters(config: SpyConfiguration, contacts: bool) -> set[int]:
    """Characters behind a finding of the last calculation: a friendly hostile contact, or a Network link."""
    stored = current()
    # after a change of the Alliance the stored result is of the old one until recalculated
    if stored is None or not config.alliance or stored.data.get("alliance_id") != config.alliance.alliance_id:
        return set()
    corporations = stored.data["corporations"]
    if contacts:
        return {
            character_id
            for corporation in corporations
            for suspect in (*corporation["suspects"], *corporation.get("visitors", []))
            for marker in suspect["markers"]
            if marker["kind"] == CONTACTS
            for character_id in marker.get("character_ids", [])
        }
    return {
        link[0] for corporation in corporations for account in corporation.get("connections", []) for link in account["links"]
    }


def character_choices(config: SpyConfiguration, marked: set[int], stored=()) -> list[tuple[str, str]]:
    """The ``marked`` characters, an alt with its main, and whatever is stored already."""
    # an ignored character leaves the findings: without the stored ones it would vanish from the list
    wanted = marked | set(stored or ())
    members = roster(config)
    labels = {character_id: str(character_id) for character_id in wanted}
    for user_id, character_id, name, *_rest in members.characters:
        if character_id in wanted:
            main = members.mains[user_id]
            labels[character_id] = name if character_id == main.character_id else f"{name} ({main.character_name})"
    return [(str(character_id), label) for character_id, label in sorted(labels.items(), key=lambda row: row[1].lower())]


def network_parties(config: SpyConfiguration) -> dict:
    """EVE ID -> (name, category) of the parties of the last Network calculation; none for another Alliance's."""
    stored = current()
    if stored is None or not config.alliance or stored.data.get("alliance_id") != config.alliance.alliance_id:
        return {}
    return Report(stored).parties


def ignored_label(entry: dict) -> str:
    """'Name – reason (by, date)'; a counterpart ignored before reasons were asked for has its name alone."""
    if not entry["reason"]:
        return entry["name"]
    return f"{entry['name']} – {entry['reason']} ({entry['by']}, {entry['at']})"


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
    capital_ship_groups = forms.MultipleChoiceField(
        label=SpyConfiguration._meta.get_field("capital_ship_groups").verbose_name,
        required=False,
        help_text=SpyConfiguration._meta.get_field("capital_ship_groups").help_text,
        widget=forms.SelectMultiple(attrs={"data-eos-spy-network-search": ""}),
    )
    # free text: the choices are only what is stored, a typed text is added as an option (Tom Select's create)
    note_presets = forms.MultipleChoiceField(
        label=SpyConfiguration._meta.get_field("note_presets").verbose_name,
        required=False,
        help_text=SpyConfiguration._meta.get_field("note_presets").help_text,
        widget=forms.SelectMultiple(attrs={"data-eos-spy-network-search": "", "data-eos-spy-network-create": ""}),
    )
    ignored_contact_characters = forms.MultipleChoiceField(
        label=SpyConfiguration._meta.get_field("ignored_contact_characters").verbose_name,
        required=False,
        help_text=SpyConfiguration._meta.get_field("ignored_contact_characters").help_text,
        widget=forms.SelectMultiple(attrs={"data-eos-spy-network-search": ""}),
    )
    ignored_network_characters = forms.MultipleChoiceField(
        label=SpyConfiguration._meta.get_field("ignored_network_characters").verbose_name,
        required=False,
        help_text=SpyConfiguration._meta.get_field("ignored_network_characters").help_text,
        widget=forms.SelectMultiple(attrs={"data-eos-spy-network-search": ""}),
    )
    # only for taking one back: a counterpart is added with the button on the Network page
    ignored_network_counterparts = forms.MultipleChoiceField(
        label=SpyConfiguration._meta.get_field("ignored_network_counterparts").verbose_name,
        required=False,
        help_text=SpyConfiguration._meta.get_field("ignored_network_counterparts").help_text,
        widget=forms.SelectMultiple(attrs={"data-eos-spy-network-search": ""}),
    )
    # the parties of the stored Network (Tom Select), and the ones already stored
    highlight_counterparts = forms.MultipleChoiceField(
        label=SpyConfiguration._meta.get_field("highlight_counterparts").verbose_name,
        required=False,
        help_text=SpyConfiguration._meta.get_field("highlight_counterparts").help_text,
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
            "capital_ship_groups",
            "note_presets",
            "corp_changes_per_year",
            "lookback_days",
            "ignored_ref_types",
            "network_neutral",
            "network_blue_above",
            "network_min_connections",
            "ignored_contact_characters",
            "ignored_network_characters",
            "ignored_network_counterparts",
            "highlight_counterparts",
        ]
        widgets = {
            "network_blue_above": forms.NumberInput(attrs={"step": "0.1", "min": "-10", "max": "10"}),
            "hostile_below": forms.NumberInput(attrs={"step": "0.1", "min": "-10", "max": "10"}),
            "blue_from": forms.NumberInput(attrs={"step": "0.1", "min": "-10", "max": "10"}),
            "corp_changes_per_year": forms.NumberInput(attrs={"min": "2", "max": "50"}),
            "lookback_days": forms.NumberInput(attrs={"min": "0", "max": "3650"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ignored_ref_types"].choices = ref_type_choices(self.instance.ignored_ref_types)
        self.fields["ignored_ships"].choices = ship_choices(self.instance.ignored_ships)
        self.fields["capital_ship_groups"].choices = capital_group_choices(self.instance.capital_ship_groups)
        for name, contacts in (("ignored_contact_characters", True), ("ignored_network_characters", False)):
            self.fields[name].choices = character_choices(
                self.instance, marked_characters(self.instance, contacts), getattr(self.instance, name)
            )
        # the stored table is a dict: the field shows its IDs as selected, labelled with name, reason, who and when
        counterparts = self.instance.ignored_network_counterparts or {}
        self.fields["ignored_network_counterparts"].choices = [
            (eve_id, ignored_label(entry))
            for eve_id, entry in sorted(counterparts.items(), key=lambda row: row[1]["name"].lower())
        ]
        self.initial["ignored_network_counterparts"] = list(counterparts)
        # the stored names win: a highlight keeps the name it was saved with, as an ignored counterpart does
        parties = network_parties(self.instance)
        stored = self.instance.highlight_counterparts or {}
        self.highlight_names = {**{str(eve_id): name for eve_id, (name, _category) in parties.items()}, **stored}
        labels = {str(eve_id): f"{name} ({category_label(category)})" for eve_id, (name, category) in parties.items()}
        self.fields["highlight_counterparts"].choices = sorted(
            ((eve_id, labels.get(eve_id, name)) for eve_id, name in self.highlight_names.items()),
            key=lambda row: row[1].lower(),
        )
        self.initial["highlight_counterparts"] = list(stored)
        # the posted texts are valid choices too: clean_note_presets checks them instead
        posted = self.data.getlist("note_presets") if hasattr(self.data, "getlist") else []
        presets = dict.fromkeys([*(self.instance.note_presets or ()), *posted])
        self.fields["note_presets"].choices = [(text, text) for text in presets]
        disabled = self.instance.disabled_markers or ()
        self.fields["markers"].initial = [kind for kind in KINDS if kind not in disabled]

    def clean_note_presets(self) -> list[str]:
        # stored as a note: whitespace collapsed as kill_note does, no longer than a note may be
        texts = [" ".join(text.split()) for text in self.cleaned_data["note_presets"]]
        if any(len(text) > KILL_NOTE_LENGTH for text in texts):
            raise forms.ValidationError(
                _("A text may have at most %(length)s characters."), params={"length": KILL_NOTE_LENGTH}
            )
        return [text for text in dict.fromkeys(texts) if text]

    # the choices are strings; EVE IDs are what the checks compare with
    def clean_ignored_contact_characters(self) -> list[int]:
        return sorted(map(int, self.cleaned_data["ignored_contact_characters"]))

    def clean_ignored_network_characters(self) -> list[int]:
        return sorted(map(int, self.cleaned_data["ignored_network_characters"]))

    def clean_ignored_network_counterparts(self) -> dict:
        # the choices are the stored IDs: what stays is a subset of the stored table, names included
        stored = self.instance.ignored_network_counterparts or {}
        return {eve_id: stored[eve_id] for eve_id in self.cleaned_data["ignored_network_counterparts"]}

    def clean_highlight_counterparts(self) -> dict:
        # the choices are the stored IDs and the Network's parties: the names come from there, never from the post
        return {eve_id: self.highlight_names[eve_id] for eve_id in self.cleaned_data["highlight_counterparts"]}

    def marker_switches(self) -> list[tuple]:
        """Each marker's checkbox with its description, for the switches of the Markers tab."""
        return [(option, DESCRIPTIONS[option.data["value"]]) for option in self["markers"]]

    def save(self, commit=True):
        self.instance.disabled_markers = [kind for kind in KINDS if kind not in self.cleaned_data["markers"]]
        return super().save(commit)
