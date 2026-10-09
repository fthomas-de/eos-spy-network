"""The hostile list, and the sources it is made from.

A contact is hostile when a ticked source holds it in aa-contacts with a
standing below the configured value. One source is enough: the Alliance may
stay neutral to an entity one of its Corporations is at war with. The
Alliance itself and its Corporations never count - a member Corporation's
quarrel with another one would otherwise mark the whole Alliance as suspects.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from django.db.models import Q

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from . import contacts
from .models import ContactSource, SpyConfiguration


@dataclass
class Hostile:
    id: int
    type: str
    name: str
    standing: Decimal
    # the names of the sources that hold it, with their standing each
    sources: list = field(default_factory=list)

    @property
    def type_label(self):
        return contacts.TYPE_LABELS.get(self.type, self.type)


def own_entity_ids(config: SpyConfiguration) -> set[int]:
    if not config.alliance:
        return set()
    corporations = EveCorporationInfo.objects.filter(alliance=config.alliance).values_list("corporation_id", flat=True)
    return {config.alliance.alliance_id, *corporations}


def hostile_entities(config: SpyConfiguration | None = None) -> list[Hostile]:
    """Every hostile, the lowest standing first."""
    config = config or SpyConfiguration.get_solo()
    own = own_entity_ids(config)
    sources = {(source.kind, source.entity_id): source for source in ContactSource.objects.all()}
    found: dict[int, Hostile] = {}
    rows = contacts.contacts(sources.values(), below=config.hostile_below)
    for row in sorted(rows, key=lambda row: (row.standing, sources[row.source].name.lower())):
        if row.contact_id in own:
            continue
        hostile = found.get(row.contact_id)
        if hostile is None:
            hostile = found[row.contact_id] = Hostile(row.contact_id, row.contact_type, row.name, row.standing)
        hostile.standing = min(hostile.standing, row.standing)
        hostile.name = hostile.name or row.name
        source = sources[row.source]
        hostile.sources.append((source.name or str(source.entity_id), row.standing))
    return sorted(found.values(), key=lambda hostile: (hostile.standing, hostile.name.lower(), hostile.id))


@dataclass
class HostileIndex:
    """Which EVE IDs count as hostile, and on whose account.

    A hostile Corporation or Alliance also makes its members hostile - but
    only those Auth knows: the app makes no ESI call, and corptools leaves
    the affiliation of the names it stores empty. A character Auth has never
    seen is hostile only when it is a contact itself.
    """

    # every hostile ID, mapped to the one that makes it hostile (itself for a contact)
    owner: dict = field(default_factory=dict)
    names: dict = field(default_factory=dict)

    def __contains__(self, entity_id) -> bool:
        return entity_id in self.owner

    def __bool__(self) -> bool:
        return bool(self.owner)

    @property
    def ids(self) -> list[int]:
        return list(self.owner)

    def describe(self, entity_id: int) -> str:
        """The name, and for a member found through its group the group's name as well."""
        name = self.names.get(entity_id) or str(entity_id)
        reason = self.owner[entity_id]
        if reason == entity_id:
            return name
        return f"{name} ({self.names.get(reason) or reason})"


def hostile_index(config: SpyConfiguration | None = None) -> HostileIndex:
    config = config or SpyConfiguration.get_solo()
    index = HostileIndex()
    for hostile in hostile_entities(config):
        index.owner[hostile.id] = hostile.id
        index.names[hostile.id] = hostile.name
    groups = list(index.owner)
    if not groups:
        return index

    for corporation_id, name, alliance_id in EveCorporationInfo.objects.filter(
        alliance__alliance_id__in=groups
    ).values_list("corporation_id", "corporation_name", "alliance__alliance_id"):
        index.owner.setdefault(corporation_id, alliance_id)
        index.names.setdefault(corporation_id, name)

    for character_id, name, corporation_id, alliance_id in EveCharacter.objects.filter(
        Q(corporation_id__in=groups) | Q(alliance_id__in=groups)
    ).values_list("character_id", "character_name", "corporation_id", "alliance_id"):
        # the Corporation first: it is the closer reason
        index.owner.setdefault(character_id, corporation_id if corporation_id in index.owner else alliance_id)
        index.names.setdefault(character_id, name)
    return index


@dataclass
class SourceRow:
    """One line of the source table on the settings page."""

    kind: str
    entity_id: int
    name: str
    ticker: str
    in_alliance: bool
    source: ContactSource | None
    has_token: bool = False
    last_update: datetime | None = None
    contacts_modified: datetime | None = None
    contact_count: int = 0
    hostile_count: int = 0

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.entity_id}"

    @property
    def kind_label(self):
        return dict(ContactSource.KIND_CHOICES)[self.kind]


def source_rows(config: SpyConfiguration | None = None) -> list[SourceRow]:
    """The Alliance, its Corporations and every ticked source that is neither any more."""
    config = config or SpyConfiguration.get_solo()
    stored = {(source.kind, source.entity_id): source for source in ContactSource.objects.all()}

    candidates = []
    if config.alliance:
        alliance = config.alliance
        candidates.append(
            (ContactSource.ALLIANCE, alliance.alliance_id, alliance.alliance_name, alliance.alliance_ticker, True)
        )
        for corporation in EveCorporationInfo.objects.filter(alliance=alliance).order_by("corporation_name"):
            candidates.append(
                (
                    ContactSource.CORPORATION,
                    corporation.corporation_id,
                    corporation.corporation_name,
                    corporation.corporation_ticker,
                    True,
                )
            )
    offered = {(kind, entity_id) for kind, entity_id, *_rest in candidates}
    for (kind, entity_id), source in sorted(stored.items(), key=lambda item: item[1].name.lower()):
        if (kind, entity_id) not in offered:
            candidates.append((kind, entity_id, source.name, "", False))

    keys = [(kind, entity_id) for kind, entity_id, *_rest in candidates]
    tokens = contacts.token_states(keys)
    # one query per kind for all rows instead of one per row
    every = contacts.contacts([ContactSource(kind=kind, entity_id=entity_id) for kind, entity_id in keys])
    totals = Counter(row.source for row in every)
    hostiles = Counter(row.source for row in every if row.standing < config.hostile_below)

    rows = []
    for kind, entity_id, name, ticker, in_alliance in candidates:
        key = (kind, entity_id)
        token = tokens.get(key)
        rows.append(
            SourceRow(
                kind=kind,
                entity_id=entity_id,
                name=name,
                ticker=ticker,
                in_alliance=in_alliance,
                source=stored.get(key),
                has_token=token is not None,
                last_update=token.last_update if token else None,
                contacts_modified=token.contacts_modified if token else None,
                contact_count=totals[key],
                hostile_count=hostiles[key],
            )
        )
    return rows


def save_sources(rows: list[SourceRow], ticked_keys) -> bool:
    """Create the ticked sources and delete the unticked ones; True when anything changed.

    Only keys of the offered rows count: a forged key cannot add a source.
    """
    ticked_keys = set(ticked_keys)
    changed = False
    for row in rows:
        if row.key in ticked_keys and row.source is None:
            ContactSource.objects.create(kind=row.kind, entity_id=row.entity_id, name=row.name)
            changed = True
        elif row.key not in ticked_keys and row.source is not None:
            row.source.delete()
            changed = True
        elif row.source is not None and row.name and row.source.name != row.name:
            # a renamed Corporation
            row.source.name = row.name
            row.source.save(update_fields=["name"])
    return changed
