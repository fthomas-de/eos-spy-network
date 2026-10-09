from django import forms
from django.utils.translation import pgettext_lazy

from allianceauth.eveonline.models import EveAllianceInfo

from .models import SpyConfiguration


class SpyConfigurationForm(forms.ModelForm):
    alliance = forms.ModelChoiceField(
        label=pgettext_lazy("EVE jargon", "Alliance"),
        queryset=EveAllianceInfo.objects.order_by("alliance_name"),
        required=False,
        help_text=SpyConfiguration._meta.get_field("alliance").help_text,
        widget=forms.Select(attrs={"data-eos-spy-network-search": ""}),
    )

    class Meta:
        model = SpyConfiguration
        fields = ["alliance", "hostile_below"]
        widgets = {"hostile_below": forms.NumberInput(attrs={"step": "0.1", "min": "-10", "max": "10"})}
