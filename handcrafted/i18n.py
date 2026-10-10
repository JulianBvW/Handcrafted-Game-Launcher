'''Translations, through gettext.

The source language is English: `_('Add to library')` is both the text and
the key. A language without a catalogue, or a text without a translation,
simply stays English.

Which language: the system's (LANGUAGE, LC_ALL, LC_MESSAGES, LANG, as
gettext reads them), unless config.json names one. setup() runs once at
startup, before any text is looked up. Texts are therefore translated at
call time, never at import -- a module-level `_('New')` would be looked up
before setup() and stay English.

Catalogues live in locale/<lang>/LC_MESSAGES/handcrafted.mo, next to the
package when run from the repository. They are built from po/ and not kept
in git.
'''

import gettext
from pathlib import Path

DOMAIN = 'handcrafted'
LOCALE_DIR = Path(__file__).resolve().parent.parent / 'locale'

_translation = gettext.NullTranslations()


def setup(language=None):
    '''Pick the catalogue. None means the system's language.'''
    global _translation
    _translation = gettext.translation(
        DOMAIN, LOCALE_DIR, languages=[language] if language else None,
        fallback=True)


def _(message):
    return _translation.gettext(message)


def ngettext(singular, plural, n):
    return _translation.ngettext(singular, plural, n)
