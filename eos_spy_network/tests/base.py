from unittest.mock import patch

from esi.models import Scope, Token

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveAllianceInfo, EveCharacter, EveCorporationInfo
from allianceauth.tests.auth_utils import AuthUtils

from eos_spy_network.models import SpyConfiguration

ALLIANCE_ID = 3001
OTHER_ALLIANCE_ID = 3999


def ticker(prefix, entity_id):
    # MySQL refuses a ticker over five characters, which real EVE IDs give
    return f"{prefix}{str(entity_id)[-4:]}"


# django-solo keeps the configuration in the cache named by SOLO_CACHE - on
# the dev instance its own Redis. The test transaction rolls back, the cache
# does not: what one test stored would leak into the next, and into the
# running instance. A cache in memory, emptied before every test, keeps them
# apart.
@override_settings(
    SOLO_CACHE=None,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "eos-spy-network"}},
)
class SpyTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        # the dev instance's broker is real: a queued task would run in its worker, against aa_dev
        patcher = patch("eos_spy_network.views.update_snapshot")
        self.update_snapshot = patcher.start()
        self.addCleanup(patcher.stop)


def make_alliance(alliance_id=ALLIANCE_ID):
    alliance, _ = EveAllianceInfo.objects.get_or_create(
        alliance_id=alliance_id,
        defaults={
            "alliance_name": f"Alliance {alliance_id}",
            "alliance_ticker": ticker("A", alliance_id),
            "executor_corp_id": 0,
        },
    )
    return alliance


def make_corporation(corporation_id, alliance_id=ALLIANCE_ID):
    alliance = make_alliance(alliance_id) if alliance_id else None
    corporation, _ = EveCorporationInfo.objects.get_or_create(
        corporation_id=corporation_id,
        defaults={
            "corporation_name": f"Corp {corporation_id}",
            "corporation_ticker": ticker("C", corporation_id),
            "member_count": 1,
            "alliance": alliance,
        },
    )
    return corporation


def make_user(name, *perms, corporation_id=2001, alliance_id=ALLIANCE_ID):
    """A user with a main character; permissions as 'app.codename'."""
    user = AuthUtils.create_user(name)
    # Alliance Auth wraps every url_hook view in main_character_required:
    # without a main, a permitted user is sent to the dashboard as well
    main = AuthUtils.add_main_character_2(
        user,
        f"{name} main",
        character_id=user.pk + 1000,
        corp_id=corporation_id,
        corp_name=f"Corp {corporation_id}",
        corp_ticker=ticker("C", corporation_id),
        alliance_id=alliance_id,
        alliance_name=f"Alliance {alliance_id}" if alliance_id else "",
    )
    # AuthUtils leaves the ownership out; a real account always has it
    CharacterOwnership.objects.create(user=user, character=main, owner_hash=f"hash-{main.character_id}")
    if perms:
        AuthUtils.add_permissions_to_user_by_name(list(perms), user)
    # has_perm caches on the instance; tests want the stored permissions
    return type(user).objects.get(pk=user.pk)


def make_character(character_id, corporation_id=2001, alliance_id=ALLIANCE_ID):
    return EveCharacter.objects.create(
        character_id=character_id,
        character_name=f"Char {character_id}",
        corporation_id=corporation_id,
        corporation_name=f"Corp {corporation_id}",
        corporation_ticker=ticker("C", corporation_id),
        alliance_id=alliance_id,
        alliance_name=f"Alliance {alliance_id}" if alliance_id else "",
    )


def make_token(character, scopes, user=None):
    token = Token.objects.create(
        character_id=character.character_id,
        character_name=character.character_name,
        character_owner_hash=f"hash-{character.character_id}",
        access_token="access",
        user=user,
    )
    token.scopes.set([Scope.objects.get_or_create(name=scope, defaults={"help_text": ""})[0] for scope in scopes])
    return token


def configure(alliance_id=ALLIANCE_ID, **fields):
    config = SpyConfiguration.get_solo()
    config.alliance = make_alliance(alliance_id) if alliance_id else None
    for name, value in fields.items():
        setattr(config, name, value)
    config.save()
    return config


def add_token(kind, entity_id, contacts_modified=True):
    """aa-contacts' token for the Alliance or a Corporation, as its own page adds it."""
    from aa_contacts.models import AllianceToken, CorporationToken

    # one character per token, apart for an Alliance and a Corporation of the same number
    character = make_character((7_000_000 if kind == "alliance" else 8_000_000) + entity_id)
    token = make_token(character, [])
    modified = timezone.now() if contacts_modified else None
    if kind == "alliance":
        return AllianceToken.objects.create(
            alliance=make_alliance(entity_id), token=token, last_modified_contacts=modified
        )
    return CorporationToken.objects.create(
        corporation=make_corporation(entity_id), token=token, last_modified_contacts=modified
    )


def add_contact(kind, entity_id, contact_id, standing, contact_type="corporation"):
    """One contact as aa-contacts' task stores it."""
    from aa_contacts.models import AllianceContact, CorporationContact

    if kind == "alliance":
        return AllianceContact.objects.create(
            alliance=make_alliance(entity_id), contact_id=contact_id, contact_type=contact_type, standing=standing
        )
    return CorporationContact.objects.create(
        corporation=make_corporation(entity_id), contact_id=contact_id, contact_type=contact_type, standing=standing
    )
