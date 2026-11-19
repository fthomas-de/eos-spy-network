"""The contracts behind the contract payments of one own character and one counterpart.

The ISK marker lists wallet entries per character and hostile; for a contract
payment (``contract_price`` ...) corptools' journal names the contract in
``context_id``. This reads those contracts with their items, for the popup -
live from corptools, once per click, never stored in the snapshot.
"""

from django.db.models import Q

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from .markers import CONTRACT_REF_TYPES, character_audits
from .models import CapitalContract


def _with_details(queryset):
    return queryset.select_related(
        "issuer_name",
        "issuer_corporation_name",
        "assignee_name",
        "acceptor_name",
        "start_location_name",
        "end_location_name",
    ).prefetch_related("contractitem_set__type_name")


def contract(contract_id: int) -> list[dict]:
    """One capital contract by ID, in the shape of ``details()`` so the popup template renders it unchanged.

    It comes from the sweep's own table, not from corptools. The template only looks attributes up, and a
    dict answers the same lookups. A contract the sweep dropped since comes back with ``contract`` None.
    """
    stored = CapitalContract.objects.filter(contract_id=contract_id).first()
    if stored is None:
        return [{"contract_id": contract_id, "contract": None, "payments": []}]
    issuer = EveCharacter.objects.filter(character_id=stored.issuer_id).values_list("character_name", flat=True).first()
    corporation = (
        EveCorporationInfo.objects.filter(corporation_id=stored.issuer_corporation_id)
        .values_list("corporation_name", flat=True)
        .first()
    )
    shown = {
        "contract_type": stored.contract_type,
        "status": "outstanding",
        "title": stored.title,
        "issuer_name": {"name": issuer},
        "issuer_corporation_name": {"name": corporation},
        "date_issued": stored.date_issued,
        "price": stored.price,
        "start_location_name": {"location_name": stored.location} if stored.location else None,
        "contractitem_set": {
            "all": [
                {"type_name": {"name": item.type.name}, "quantity": item.quantity, "is_included": item.is_included}
                for item in stored.items.select_related("type")
            ]
        },
    }
    return [{"contract_id": contract_id, "contract": shown, "payments": []}]


def details(character_id: int, counterpart_id: int, since=None, ignored=()) -> list[dict]:
    """The contracts of the character's payments with the counterpart, the latest first.

    ``since`` and ``ignored`` are the time frame and the ignored wallet entry
    types of the settings: the popup shows what the row counted, no more.
    A payment whose contract corptools never stored comes back with
    ``contract`` None, so the viewer sees that something is missing.
    """
    from corptools.models import CharacterWalletJournalEntry, Contract

    audits = character_audits([character_id])
    if not audits:
        return []

    entries = CharacterWalletJournalEntry.objects.filter(
        Q(first_party_id=counterpart_id) | Q(second_party_id=counterpart_id),
        character_id__in=list(audits),
        ref_type__in=[ref_type for ref_type in CONTRACT_REF_TYPES if ref_type not in ignored],
    )
    if since is not None:
        entries = entries.filter(date__gte=since)

    payments = {}  # contract ID -> [payment, ...]
    for context_id, ref_type, amount, date in entries.order_by("-date").values_list(
        "context_id", "ref_type", "amount", "date"
    ):
        if context_id:
            payments.setdefault(context_id, []).append(
                {"ref_type": ref_type.replace("_", " "), "amount": amount, "date": date}
            )

    stored = {
        contract.contract_id: contract
        for contract in _with_details(
            Contract.objects.filter(character_id__in=list(audits), contract_id__in=list(payments))
        )
    }
    # entries came newest first and dicts keep that order
    return [
        {"contract_id": contract_id, "contract": stored.get(contract_id), "payments": rows}
        for contract_id, rows in payments.items()
    ]
