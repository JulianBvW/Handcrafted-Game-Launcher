'''Playtime and dates as text.

    /usr/bin/python3 tests/test_formatting.py
'''

import locale
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from harness import check, report, section

from handcrafted import formatting, i18n


def ts(*args):
    '''Local time to a Unix timestamp.'''
    return datetime(*args).timestamp()


section('Playtime')

for seconds, expected in ((0, '0h'), (59, '0h'), (60, '1m'), (2700, '45m'),
                          (3599, '59m'), (3600, '1h 0m'), (85200, '23h 40m'),
                          (231300, '64h 15m'), (-5, '0h')):
    got = formatting.playtime(seconds)
    check(f'{seconds} s is {expected}', got == expected, got)

section('Last played, by calendar day')

now = ts(2026, 10, 10, 15, 0)


def days_ago(days):
    moment = datetime(2026, 10, 10, 15, 0) - timedelta(days=days)
    return formatting.last_played(moment.timestamp(), now=now)


check('None is Never', formatting.last_played(None, now=now) == 'Never')
for days, expected in ((0, 'Today'), (1, 'Yesterday'), (2, '2 days ago'),
                       (6, '6 days ago'), (7, 'Last week'),
                       (13, 'Last week'), (14, '2 weeks ago'),
                       (29, '4 weeks ago'), (30, 'Last month'),
                       (59, 'Last month'), (60, '2 months ago'),
                       (359, '11 months ago'), (364, '11 months ago'),
                       (365, 'Last year'),
                       (729, 'Last year'), (730, '2 years ago'),
                       (1200, '3 years ago')):
    got = days_ago(days)
    check(f'{days} days back is {expected}', got == expected, got)

got = formatting.last_played(ts(2026, 10, 9, 23, 50),
                             now=ts(2026, 10, 10, 0, 10))
check('23:50 is Yesterday at 00:10', got == 'Yesterday', got)

got = formatting.last_played(ts(2026, 10, 10, 0, 5),
                             now=ts(2026, 10, 10, 23, 55))
check('00:05 is still Today at 23:55', got == 'Today', got)

got = formatting.last_played(now + 86400 * 3, now=now)
check('a moment in the future is Today', got == 'Today', got)

section('Added')

check('5 Mar 2026', formatting.added(ts(2026, 3, 5, 12)) == '5 Mar 2026')
check('31 Dec 2025', formatting.added(ts(2025, 12, 31, 23, 59))
      == '31 Dec 2025')

try:
    locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
    german = True
except locale.Error:
    german = False
if german:
    got = formatting.added(ts(2026, 3, 5, 12))
    check('stays English under a German locale', got == '5 Mar 2026', got)
    locale.setlocale(locale.LC_TIME, 'C')
else:
    print('  SKIP  no de_DE.UTF-8 locale on this machine')

section('Through a translation')

# A small German catalogue, built the way the real one will be: a .po file
# compiled by msgfmt. Proves the chain from _() and ngettext() to the text.
CATALOGUE = r'''
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

msgid "{n} day ago"
msgid_plural "{n} days ago"
msgstr[0] "vor {n} Tag"
msgstr[1] "vor {n} Tagen"

msgid "Mar"
msgstr "Mär"

msgid "{day} {month} {year}"
msgstr "{day}. {month} {year}"
'''

if shutil.which('msgfmt'):
    folder = Path(tempfile.mkdtemp(prefix='handcrafted-i18n-'))
    messages = folder / 'de' / 'LC_MESSAGES'
    messages.mkdir(parents=True)
    (folder / 'de.po').write_text(CATALOGUE, encoding='utf-8')
    subprocess.run(['msgfmt', '-o', str(messages / 'handcrafted.mo'),
                    str(folder / 'de.po')], check=True)
    i18n.LOCALE_DIR = folder
    i18n.setup('de')
    got = days_ago(3)
    check('plural through the catalogue', got == 'vor 3 Tagen', got)
    got = formatting.added(ts(2026, 3, 5, 12))
    check('month and pattern through the catalogue',
          got == '5. Mär 2026', got)
    got = formatting.last_played(None)
    check('an untranslated text stays English', got == 'Never', got)
    i18n.setup('xx')
    check('a language without a catalogue is English', days_ago(3)
          == '3 days ago')
    shutil.rmtree(folder)
else:
    print('  SKIP  no msgfmt on this machine')

report()
