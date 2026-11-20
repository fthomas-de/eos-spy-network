"""The daily sweep of the public contracts for the marker *Capital in contract*.

ESI lists the open public contracts per region, 1000 to a page, with the issuer's Corporation. The sweep
walks all regions of known space, keeps the contracts of the Alliance's Corporations and fetches the items
of each of those once: a contract's items never change. It needs no token and no other app, only the
public endpoints; the marker reads what it stores.
"""

from esi.exceptions import ESIErrorLimitException
from esi.openapi_clients import ESIClientProvider
from eve_sde.models import NPCStation, Region

from django.db import transaction
from django.utils import timezone

from allianceauth.eveonline import __esi_compatibility_date__
from allianceauth.eveonline.models import EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger

from . import __version__
from .models import CapitalContract, CapitalContractItem, SpyConfiguration

logger = get_extension_logger(__name__)

# Alliance Auth's own provider loads a fixed list of operations; these two are not on it
esi = ESIClientProvider(
    compatibility_date=__esi_compatibility_date__,
    ua_appname="eos-spy-network",
    ua_version=__version__,
    ua_url="https://github.com/fthomas-de/eos-spy-network",
    operations=["GetContractsPublicRegionId", "GetContractsPublicItemsContractId"],
)

# wormhole space starts at 11000000 and has no stations to put a contract in
KNOWN_SPACE_BELOW = 11_000_000
# a courier or a loan holds no ship
SHIP_CONTRACTS = ("item_exchange", "auction")


# No ETag: a 304 carries no list, and without the list the sweep cannot tell which contracts are gone; a
# contract listed again after its row went would get a 304 for its items and never be stored. No cache
# either: nobody reads a page again before it expires.
def _region_contracts(region_id: int) -> list:
    return esi.client.Contracts.GetContractsPublicRegionId(region_id=region_id).results(
        use_etag=False, store_cache=False
    )


def _contract_items(contract_id: int) -> list:
    return esi.client.Contracts.GetContractsPublicItemsContractId(contract_id=contract_id).results(
        use_etag=False, store_cache=False
    )


def sweep() -> int:
    """Store the open public contracts of the Alliance's Corporations; returns how many are new.

    A contract no longer listed is gone (accepted, withdrawn), but only when every region answered:
    a region that failed must not make its contracts vanish. An expired one goes in any case.
    ESI's error limit stops the sweep with ``ESIErrorLimitException``: every further call would fail at
    once, the task tries again after the reset.
    """
    config = SpyConfiguration.get_solo()
    if not config.alliance:
        return 0
    corporations = set(
        EveCorporationInfo.objects.filter(alliance=config.alliance).values_list("corporation_id", flat=True)
    )
    now = timezone.now()
    seen = {}  # contract ID -> (the row, its region's name)
    regions = list(Region.objects.filter(id__lt=KNOWN_SPACE_BELOW).order_by("id").values_list("id", "name"))
    # django-esi 10 retries no timeout (aiopenapi3 wraps it), so a failed region gets a second try at the end
    for _attempt in range(2):
        failed = []
        for region_id, region_name in regions:
            try:
                listed = _region_contracts(region_id)
            except ESIErrorLimitException:
                raise
            # any other error - HTTP, timeout, ESI down - only costs this region until the next sweep
            except Exception as error:  # noqa: BLE001
                logger.warning("ESI public contracts of region %s failed: %s", region_id, error)
                failed.append((region_id, region_name))
                continue
            for row in listed:
                if row.issuer_corporation_id in corporations and row.type in SHIP_CONTRACTS and row.date_expired > now:
                    seen[row.contract_id] = (row, region_name)
        regions = failed

    known = set(CapitalContract.objects.filter(pk__in=list(seen)).values_list("pk", flat=True))
    new = {contract_id: found for contract_id, found in seen.items() if contract_id not in known}
    stations = dict(
        NPCStation.objects.filter(
            id__in=[row.start_location_id for row, _region in new.values() if row.start_location_id]
        ).values_list("id", "name")
    )
    added = 0
    for contract_id, (row, region_name) in new.items():
        try:
            items = _contract_items(contract_id)
        except ESIErrorLimitException:
            raise
        except Exception as error:  # noqa: BLE001
            logger.warning("ESI items of public contract %s failed: %s", contract_id, error)
            continue
        station = stations.get(row.start_location_id)
        # a structure's name needs a token with docking rights: it shows as its ID
        place = station or (f"structure {row.start_location_id}" if row.start_location_id else "")
        with transaction.atomic():
            contract = CapitalContract.objects.create(
                contract_id=contract_id,
                issuer_id=row.issuer_id,
                issuer_corporation_id=row.issuer_corporation_id,
                contract_type=row.type,
                title=(row.title or "")[:254],
                price=row.price,
                buyout=row.buyout,
                date_issued=row.date_issued,
                date_expired=row.date_expired,
                location=f"{region_name}, {place}" if place else region_name,
            )
            CapitalContractItem.objects.bulk_create(
                CapitalContractItem(
                    contract=contract, type_id=item.type_id, quantity=item.quantity, is_included=item.is_included
                )
                for item in items
            )
        added += 1

    CapitalContract.objects.filter(date_expired__lte=now).delete()
    if not failed:
        CapitalContract.objects.exclude(pk__in=list(seen)).delete()
    return added
