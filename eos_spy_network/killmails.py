"""Killmails of the own characters, read from killtracker.

killtracker keeps the killmails it receives from zKillboard in its own
tables only with ``KILLTRACKER_STORING_KILLMAILS_ENABLED`` and deletes them
after ``KILLTRACKER_PURGE_KILLMAILS_AFTER_DAYS``: the blue kills reach back
no further than that, whatever the time frame says. Its trackers keep
nothing, they only post to Discord. killtracker is optional, not a
dependency: without it, or without stored killmails, there are no blue kills
and the pages say why.
"""

from dataclasses import dataclass
from datetime import datetime

from django.apps import apps
from django.db.models import Q

APP = "killtracker"


def is_installed() -> bool:
    return apps.is_installed(APP)


def is_storing() -> bool:
    """killtracker keeps its killmails; read through its own settings module, which holds its default."""
    if not is_installed():
        return False
    from killtracker.app_settings import KILLTRACKER_STORING_KILLMAILS_ENABLED

    return bool(KILLTRACKER_STORING_KILLMAILS_ENABLED)


@dataclass
class Kill:
    """One own character on the attackers of one killmail."""

    killmail_id: int
    time: datetime
    attacker_id: int
    victim_id: int | None
    victim_name: str
    victim_corporation_id: int | None
    victim_corporation: str
    victim_alliance_id: int | None
    victim_alliance: str
    ship: str
    value: float | None


def kills(character_ids, victim_alliance_id: int | None, victim_ids, since: datetime | None = None) -> list[Kill]:
    """Killmails with one of ``character_ids`` among the attackers and a victim that is in the
    Alliance ``victim_alliance_id`` or is, or belongs to, one of ``victim_ids``."""
    if not is_installed() or not character_ids:
        return []
    from killtracker.models import EveKillmailAttacker

    victim_ids = list(victim_ids)
    victims = Q(killmail__character_id__in=victim_ids) | Q(killmail__corporation_id__in=victim_ids)
    victims |= Q(killmail__alliance_id__in=victim_ids)
    if victim_alliance_id:
        victims |= Q(killmail__alliance_id=victim_alliance_id)
    attackers = EveKillmailAttacker.objects.filter(victims, character_id__in=list(character_ids))
    if since is not None:
        attackers = attackers.filter(killmail__time__gte=since)
    # killtracker stores a killmail first and resolves its names later: an empty name is a fresh one
    return [
        Kill(
            killmail_id,
            time,
            attacker_id,
            victim_id,
            victim or "",
            corporation_id,
            corporation or "",
            alliance_id,
            alliance or "",
            ship or "",
            value,
        )
        for (
            killmail_id,
            time,
            attacker_id,
            victim_id,
            victim,
            corporation_id,
            corporation,
            alliance_id,
            alliance,
            ship,
            value,
        ) in attackers.values_list(
            "killmail_id",
            "killmail__time",
            "character_id",
            "killmail__character_id",
            "killmail__character__name",
            "killmail__corporation_id",
            "killmail__corporation__name",
            "killmail__alliance_id",
            "killmail__alliance__name",
            "killmail__ship_type__name",
            "killmail__total_value",
        )
    ]
