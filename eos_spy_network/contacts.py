"""Contacts of the Alliance and its Corporations, read from aa-contacts.

aa-contacts fetches them from ESI with the tokens added on its own page and
keeps them up to date with its own task; this app only reads its tables.
aa-contacts is optional, not a dependency: without it the hostile list is
empty and the pages say why.

Names come through aa-contacts' ``with_contact_name()``, a subquery on Auth's
own tables. Never its ``contact_name`` property: for an entity Auth does not
know yet, it creates the row from ESI - a write in the middle of a page view.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.apps import apps
from django.utils.translation import pgettext_lazy

from .models import ContactSource

APP = "aa_contacts"

TYPE_LABELS = {
    "character": pgettext_lazy("EVE jargon", "Character"),
    "corporation": pgettext_lazy("EVE jargon", "Corporation"),
    "alliance": pgettext_lazy("EVE jargon", "Alliance"),
    "faction": pgettext_lazy("EVE jargon", "Faction"),
}


def is_installed() -> bool:
    return apps.is_installed(APP)


@dataclass
class Contact:
    source: tuple  # (kind, entity_id)
    contact_id: int
    contact_type: str
    name: str
    standing: Decimal


@dataclass
class TokenState:
    # when aa-contacts last tried, and the Last-Modified of the contacts it
    # holds - None until its task has read them once
    last_update: datetime | None
    contacts_modified: datetime | None


def _models(kind: str):
    """(contact model, token model, lookup from either to the entity's EVE ID)."""
    from aa_contacts.models import AllianceContact, AllianceToken, CorporationContact, CorporationToken

    if kind == ContactSource.ALLIANCE:
        return AllianceContact, AllianceToken, "alliance__alliance_id"
    return CorporationContact, CorporationToken, "corporation__corporation_id"


def _standing(value: float) -> Decimal:
    # a FloatField in aa-contacts; two places are all a standing has
    return Decimal(str(round(value, 2)))


def token_states(keys) -> dict[tuple, TokenState]:
    """aa-contacts' token per (kind, entity_id); a key without token is left out."""
    if not is_installed():
        return {}
    found = {}
    for kind in (ContactSource.ALLIANCE, ContactSource.CORPORATION):
        entity_ids = [entity_id for key_kind, entity_id in keys if key_kind == kind]
        if not entity_ids:
            continue
        _contact_model, token_model, entity = _models(kind)
        for entity_id, last_update, modified in token_model.objects.filter(
            **{f"{entity}__in": entity_ids}
        ).values_list(entity, "last_update", "last_modified_contacts"):
            found[(kind, entity_id)] = TokenState(last_update, modified)
    return found


def contacts(sources, below: Decimal | None = None) -> list[Contact]:
    """The contacts the sources hold in aa-contacts; with ``below``, only those with a lower standing."""
    if not is_installed():
        return []
    found = []
    for kind in (ContactSource.ALLIANCE, ContactSource.CORPORATION):
        entity_ids = [source.entity_id for source in sources if source.kind == kind]
        if not entity_ids:
            continue
        contact_model, _token_model, entity = _models(kind)
        rows = contact_model.objects.with_contact_name().filter(**{f"{entity}__in": entity_ids})
        if below is not None:
            rows = rows.filter(standing__lt=below)
        for entity_id, contact_id, contact_type, name, standing in rows.values_list(
            entity, "contact_id", "contact_type", "contact_name_annotation", "standing"
        ):
            found.append(Contact((kind, entity_id), contact_id, contact_type, name or "", _standing(standing)))
    return found
