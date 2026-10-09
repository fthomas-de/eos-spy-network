import gettext
import importlib.util
from pathlib import Path
from unittest import skipUnless

from django.test import tag
from django.utils import translation

import eos_spy_network

from .base import SpyTestCase

LOCALE = Path(eos_spy_network.__file__).parent / "locale"
LANGUAGES = {"de": "de", "ru": "ru", "zh_Hans": "zh-hans"}

# the repo's tools/, not part of the installed package
GLOSSARY = Path(eos_spy_network.__file__).parent.parent / "tools" / "glossary.py"


@skipUnless(GLOSSARY.exists(), "tools/glossary.py only exists in the repo")
class TestGlossary(SpyTestCase):
    """The glossary's shape, checked on every run - unlike the catalogues it
    changes with the code, and translate.py refuses a malformed one."""

    def test_should_be_well_formed(self):
        spec = importlib.util.spec_from_file_location("eos_spy_network_glossary", GLOSSARY)
        glossary = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(glossary)

        self.assertEqual(glossary.problems(), [])


# The catalogues are only brought up to date at a commit, so between commits
# these checks describe the last commit, not the code - red for a known
# reason, which only teaches everybody to ignore a red suite. The suite runs
# with --exclude-tag translations; tools/translate.py runs them with
# --tag translations after it has filled and compiled the catalogues.
@tag("translations")
class TestTranslations(SpyTestCase):
    def test_should_load_every_compiled_catalogue(self):
        # a catalogue that was not compiled falls back to English silently
        for language in LANGUAGES.values():
            with self.subTest(language), translation.override(language):
                self.assertNotEqual(translation.gettext("Mains with markers"), "Mains with markers")

    def test_should_keep_eve_jargon_english(self):
        for language in LANGUAGES.values():
            with self.subTest(language), translation.override(language):
                for word in ("Alliance", "Corporation", "Character", "Faction"):
                    self.assertEqual(translation.pgettext("EVE jargon", word), word)

    def test_should_show_our_translation_for_every_message(self):
        """Nothing another app translates differently may hide ours.

        Django merges every installed app's catalogue, and for the same msgid
        an app earlier in INSTALLED_APPS wins. Alliance Auth translates many
        short words itself, and without a context of our own the page
        silently shows its version. This asks Django what it actually shows
        for each of our entries.
        """
        for folder, language in LANGUAGES.items():
            with open(LOCALE / folder / "LC_MESSAGES" / "django.mo", "rb") as mo:
                catalogue = gettext.GNUTranslations(mo)._catalog

            with translation.override(language):
                for key, ours in catalogue.items():
                    if key == "":
                        continue
                    if isinstance(key, tuple):
                        msgid, form = key
                        if form != 0:
                            continue
                        context, _sep, msgid = msgid.rpartition("\x04")
                        shown = (
                            translation.npgettext(context, msgid, msgid, 1)
                            if context
                            else translation.ngettext(msgid, msgid, 1)
                        )
                    else:
                        context, _sep, msgid = key.rpartition("\x04")
                        shown = (
                            translation.pgettext(context, msgid)
                            if context
                            else translation.gettext(msgid)
                        )
                    with self.subTest(language=folder, msgid=msgid):
                        self.assertEqual(shown, ours)
