'''The translations in po/: complete, valid, and true to their placeholders.

    /usr/bin/python3 tests/test_translations.py

Needs xgettext and msgfmt (package gettext); without them it says so and
skips.
'''

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from harness import REPO, check, report, sandbox, section

if not (shutil.which('xgettext') and shutil.which('msgfmt')):
    print('  SKIP  no xgettext/msgfmt; sudo apt install gettext')
    sys.exit(0)

folder = sandbox()
PLACEHOLDER = re.compile(r'\{[a-z_]+\}')


def entries(path):
    '''{msgid: [msgstr, ...]} of a .po or .pot file, the header left out.
    Plural entries are keyed by their singular and carry every form.'''
    found = {}
    for block in path.read_text(encoding='utf-8').split('\n\n'):
        body = '\n'.join(line for line in block.splitlines()
                         if not line.startswith('#'))
        # msgmerge marks a changed text fuzzy and keeps the old
        # translation; msgfmt leaves fuzzy ones out, so they count as none.
        fuzzy = any(line.startswith('#,') and 'fuzzy' in line
                    for line in block.splitlines())

        def strings(keyword):
            return [''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)))
                    for m in re.finditer(rf'^{keyword} ((?:".*"\n?)+)',
                                         body + '\n', re.M)]
        msgid = strings('msgid')
        if not msgid or not msgid[0]:
            continue
        translations = strings('msgstr') + strings(r'msgstr\[\d\]')
        found[msgid[0]] = ([''] if fuzzy else translations,
                           strings('msgid_plural'))
    return found


template = Path(tempfile.mkdtemp(dir=folder)) / 'now.pot'
subprocess.run(['xgettext', '--language=Python', '--keyword=_',
                '--keyword=ngettext:1,2', '--from-code=UTF-8',
                '-o', str(template)]
               + sorted(str(p) for p in (REPO / 'handcrafted').glob('*.py')),
               check=True, capture_output=True)
in_code = entries(template)

for po in sorted((REPO / 'po').glob('*.po')):
    section(po.name)
    translated = entries(po)
    result = subprocess.run(['msgfmt', '--check', '-o', '/dev/null',
                             str(po)], capture_output=True, text=True)
    check('msgfmt finds nothing wrong', result.returncode == 0,
          result.stderr)

    missing = sorted(set(in_code) - set(translated))
    check('every text in the code is in it', not missing, missing)
    stale = sorted(set(translated) - set(in_code))
    check('and nothing the code no longer has', not stale, stale)

    empty = sorted(msgid for msgid, (strs, _) in translated.items()
                   if not strs or not all(strs))
    check('every one is translated, every plural form too', not empty,
          empty)

    wrong = []
    for msgid, (strs, plural) in translated.items():
        wanted = set(PLACEHOLDER.findall(msgid))
        for text in strs:
            if set(PLACEHOLDER.findall(text)) != wanted:
                wrong.append((msgid, text))
    check('with the same {placeholders} as the original', not wrong, wrong)

    template_plurals = {msgid for msgid, (_, plural) in in_code.items()
                        if plural}
    plurals = {msgid for msgid, (_, plural) in translated.items() if plural}
    check('plurals where the code has plurals',
          plurals == template_plurals, plurals ^ template_plurals)

report(folder)
