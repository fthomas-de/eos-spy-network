from decimal import Decimal
from unittest.mock import patch

from eos_spy_network import contacts
from eos_spy_network.models import ContactSource

from .base import ALLIANCE_ID, SpyTestCase, add_contact, add_token, make_character

ALLIANCE = ContactSource.ALLIANCE
CORPORATION = ContactSource.CORPORATION


def source(kind, entity_id):
    return ContactSource(kind=kind, entity_id=entity_id)


class TestContacts(SpyTestCase):
    def test_should_read_alliance_and_corporation_contacts(self):
        add_contact(ALLIANCE, ALLIANCE_ID, 98000001, -10.0)
        add_contact(CORPORATION, 2001, 90000001, 5.5, "character")

        found = contacts.contacts([source(ALLIANCE, ALLIANCE_ID), source(CORPORATION, 2001)])

        self.assertEqual(
            {(row.source, row.contact_id, row.contact_type, row.standing) for row in found},
            {
                ((ALLIANCE, ALLIANCE_ID), 98000001, "corporation", Decimal("-10.00")),
                ((CORPORATION, 2001), 90000001, "character", Decimal("5.50")),
            },
        )

    def test_should_read_only_the_given_sources(self):
        add_contact(CORPORATION, 2001, 1, -10.0)
        add_contact(CORPORATION, 2002, 2, -10.0)

        found = contacts.contacts([source(CORPORATION, 2002)])

        self.assertEqual([row.contact_id for row in found], [2])

    def test_should_keep_alliance_and_corporation_ids_apart(self):
        # the same number as an Alliance and as a Corporation ID
        add_contact(CORPORATION, 2001, 1, -10.0)

        self.assertEqual(contacts.contacts([source(ALLIANCE, 2001)]), [])

    def test_should_filter_by_standing(self):
        add_contact(CORPORATION, 2001, 1, -0.1)
        add_contact(CORPORATION, 2001, 2, 0.0)

        found = contacts.contacts([source(CORPORATION, 2001)], below=Decimal("0"))

        self.assertEqual([row.contact_id for row in found], [1])

    def test_should_name_contacts_auth_knows_without_creating_any(self):
        character = make_character(90000001)
        add_contact(CORPORATION, 2001, character.character_id, -10.0, "character")
        add_contact(CORPORATION, 2001, 90000002, -10.0, "character")

        with patch("allianceauth.eveonline.models.EveCharacter.objects.create_character") as create:
            found = contacts.contacts([source(CORPORATION, 2001)])

        create.assert_not_called()
        self.assertEqual(
            {row.contact_id: row.name for row in found}, {90000001: "Char 90000001", 90000002: ""}
        )

    def test_should_ask_django_whether_aa_contacts_is_installed(self):
        with patch("eos_spy_network.contacts.apps.is_installed", return_value=False) as installed:
            self.assertFalse(contacts.is_installed())

        installed.assert_called_once_with("aa_contacts")
        self.assertTrue(contacts.is_installed())

    def test_should_read_nothing_without_aa_contacts(self):
        add_contact(CORPORATION, 2001, 1, -10.0)

        with patch("eos_spy_network.contacts.is_installed", return_value=False):
            self.assertEqual(contacts.contacts([source(CORPORATION, 2001)]), [])
            self.assertEqual(contacts.token_states([(CORPORATION, 2001)]), {})


class TestTokenStates(SpyTestCase):
    def test_should_report_the_tokens_of_the_given_keys(self):
        add_token(ALLIANCE, ALLIANCE_ID)
        add_token(CORPORATION, 2001, contacts_modified=False)
        add_token(CORPORATION, 2002)

        states = contacts.token_states([(ALLIANCE, ALLIANCE_ID), (CORPORATION, 2001), (CORPORATION, 2003)])

        self.assertEqual(set(states), {(ALLIANCE, ALLIANCE_ID), (CORPORATION, 2001)})
        self.assertIsNotNone(states[(ALLIANCE, ALLIANCE_ID)].contacts_modified)
        self.assertIsNone(states[(CORPORATION, 2001)].contacts_modified)
