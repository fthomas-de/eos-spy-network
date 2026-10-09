"""Which Corporation and Alliance a counterpart outside the Alliance belongs to.

The network graph follows a counterpart up to its Corporation and Alliance:
that is where a hostile standing usually sits, not on the character. What
Auth and corptools already hold comes first; only what neither knows is
asked from ESI, through its public endpoints (names, character affiliation,
Corporation) without a token. Only the task calls this, never a page view.

A failed ESI request costs the affiliation, never the calculation: the
counterpart then ends at itself in the graph.
"""

from dataclasses import dataclass

from django.apps import apps

from allianceauth.eveonline.models import EveAllianceInfo, EveCharacter, EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger

logger = get_extension_logger(__name__)

CHARACTER = "character"
CORPORATION = "corporation"
ALLIANCE = "alliance"
# ESI takes at most 1000 IDs per names or affiliation request
CHUNK = 1000


@dataclass
class Entity:
    id: int
    name: str = ""
    category: str = ""  # character, corporation, alliance; empty while unknown
    corporation_id: int | None = None
    alliance_id: int | None = None


def _chunks(ids: list) -> list[list]:
    return [ids[start : start + CHUNK] for start in range(0, len(ids), CHUNK)]


def _esi_names(ids: list[int]) -> dict[int, tuple[str, str]]:
    """ID -> (name, category) from ESI; whatever a failed request held stays out."""
    from allianceauth.eveonline.providers import open_api_provider

    found = {}
    for chunk in _chunks(ids):
        try:
            for row in open_api_provider.post_names(chunk):
                found[row.id] = (row.name, row.category)
        # any error - HTTP, timeout, ESI down - only costs the names of this chunk
        except Exception as error:  # noqa: BLE001
            logger.warning("ESI names lookup failed for %d IDs: %s", len(chunk), error)
    return found


def _esi_affiliations(character_ids: list[int]) -> dict[int, tuple[int, int | None]]:
    """Character ID -> (Corporation ID, Alliance ID) from ESI."""
    from allianceauth.eveonline.providers import open_api_provider

    found = {}
    for chunk in _chunks(character_ids):
        try:
            rows, _response = open_api_provider.get_affiliations(chunk)
            for row in rows:
                found[row.character_id] = (row.corporation_id, getattr(row, "alliance_id", None) or None)
        except Exception as error:  # noqa: BLE001
            logger.warning("ESI affiliation lookup failed for %d characters: %s", len(chunk), error)
    return found


def _esi_corporation_alliance(corporation_id: int) -> int | None:
    from allianceauth.eveonline.providers import open_api_provider

    try:
        corporation, _response = open_api_provider.get_corporation(corporation_id)
    except Exception as error:  # noqa: BLE001
        logger.warning("ESI Corporation lookup failed for %s: %s", corporation_id, error)
        return None
    return getattr(corporation, "alliance_id", None) or None


def resolve(ids) -> dict[int, Entity]:
    """Each ID with its category and affiliation, plus every Corporation and Alliance on the way."""
    entities: dict[int, Entity] = {}

    def entity(eve_id, **fields) -> Entity:
        found = entities.setdefault(eve_id, Entity(eve_id))
        for name, value in fields.items():
            if value and not getattr(found, name):
                setattr(found, name, value)
        return found

    ids = {eve_id for eve_id in ids if eve_id}
    for eve_id in ids:
        # an ID nobody knows still gets an entry: its ID is its name
        entity(eve_id)
    for row in EveCharacter.objects.filter(character_id__in=ids).values(
        "character_id", "character_name", "corporation_id", "corporation_name", "alliance_id", "alliance_name"
    ):
        entity(
            row["character_id"],
            name=row["character_name"],
            category=CHARACTER,
            corporation_id=row["corporation_id"],
            alliance_id=row["alliance_id"],
        )
        entity(row["corporation_id"], name=row["corporation_name"], category=CORPORATION, alliance_id=row["alliance_id"])
        if row["alliance_id"]:
            entity(row["alliance_id"], name=row["alliance_name"], category=ALLIANCE)
    _known_groups(entity, ids)

    if apps.is_installed("corptools"):
        from corptools.models import EveName

        unknown = [eve_id for eve_id in ids if not entities.get(eve_id, Entity(eve_id)).category]
        # corptools usually leaves corporation and alliance empty; when it has them they count
        for row in EveName.objects.filter(eve_id__in=unknown).values(
            "eve_id", "name", "category", "corporation_id", "alliance_id"
        ):
            entity(
                row["eve_id"],
                name=row["name"],
                category=row["category"],
                corporation_id=row["corporation_id"],
                alliance_id=row["alliance_id"],
            )

    unknown = [eve_id for eve_id in ids if not entities.get(eve_id, Entity(eve_id)).category]
    for eve_id, (name, category) in (_esi_names(unknown) if unknown else {}).items():
        if eve_id in ids:
            entity(eve_id, name=name, category=category)

    characters = [
        eve_id
        for eve_id in ids
        if entities.get(eve_id) and entities[eve_id].category == CHARACTER and not entities[eve_id].corporation_id
    ]
    for character_id, (corporation_id, alliance_id) in (_esi_affiliations(characters) if characters else {}).items():
        if character_id not in ids:
            continue
        entity(character_id, corporation_id=corporation_id, alliance_id=alliance_id)
        entity(corporation_id, category=CORPORATION, alliance_id=alliance_id)
        if alliance_id:
            entity(alliance_id, category=ALLIANCE)

    groups = {
        group_id
        for found in list(entities.values())
        for group_id in (found.corporation_id, found.alliance_id)
        if group_id
    } | {found.id for found in entities.values() if found.category in (CORPORATION, ALLIANCE)}
    for group_id in groups:
        entity(group_id)
    _known_groups(entity, groups)

    # a Corporation counterpart, or a character's Corporation Auth does not know: its Alliance
    for found in list(entities.values()):
        if found.category == CORPORATION and found.alliance_id is None and found.id in ids:
            alliance_id = _esi_corporation_alliance(found.id)
            if alliance_id:
                found.alliance_id = alliance_id
                entity(alliance_id, category=ALLIANCE)
    for found in entities.values():
        if found.category == CHARACTER and found.corporation_id and not found.alliance_id:
            found.alliance_id = entities[found.corporation_id].alliance_id

    _fill_names(entities)
    return entities


def _known_groups(entity, ids) -> None:
    """Corporations and Alliances Auth knows, with the Corporation's Alliance."""
    for row in EveCorporationInfo.objects.filter(corporation_id__in=ids).values(
        "corporation_id", "corporation_name", "alliance__alliance_id", "alliance__alliance_name"
    ):
        entity(
            row["corporation_id"],
            name=row["corporation_name"],
            category=CORPORATION,
            alliance_id=row["alliance__alliance_id"],
        )
        if row["alliance__alliance_id"]:
            entity(row["alliance__alliance_id"], name=row["alliance__alliance_name"], category=ALLIANCE)
    for alliance_id, name in EveAllianceInfo.objects.filter(alliance_id__in=ids).values_list(
        "alliance_id", "alliance_name"
    ):
        entity(alliance_id, name=name, category=ALLIANCE)


def _fill_names(entities: dict[int, Entity]) -> None:
    """Names still missing: corptools' names, then ESI, else the ID."""
    missing = [eve_id for eve_id, found in entities.items() if not found.name]
    if missing and apps.is_installed("corptools"):
        from corptools.models import EveName

        for eve_id, name in EveName.objects.filter(eve_id__in=missing).values_list("eve_id", "name"):
            entities[eve_id].name = name
        missing = [eve_id for eve_id in missing if not entities[eve_id].name]
    for eve_id, (name, category) in (_esi_names(missing) if missing else {}).items():
        if eve_id not in entities:
            continue
        entities[eve_id].name = name
        entities[eve_id].category = entities[eve_id].category or category
    for found in entities.values():
        found.name = found.name or str(found.id)
