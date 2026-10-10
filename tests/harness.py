'''The little bit of scaffolding the test scripts share.

No pytest: Handcrafted needs nothing beyond what Linux Mint ships, and a
test suite that breaks that promise is a strange way to defend it. Run a
test file directly; it exits non-zero if any check failed.
'''

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_ok = 0
_failed = 0


def check(name, condition, detail=''):
    global _ok, _failed
    if condition:
        _ok += 1
        print(f'  PASS  {name}')
    else:
        _failed += 1
        print(f'  FAIL  {name}  {detail}')


def section(title):
    print(f'\n{title}')


def sandbox():
    '''A config folder of our own, so ~/.config/handcrafted is never touched.

    Patches the paths in config, which config.py and state.py read at call
    time rather than import time -- that is what makes this possible at all.
    '''
    from handcrafted import config
    folder = Path(tempfile.mkdtemp(prefix='handcrafted-test-'))
    config.CONFIG_DIR = folder
    config.CONFIG_FILE = folder / 'config.json'
    config.STATE_FILE = folder / 'state.json'
    config._apply_user_config()
    return folder


def report(folder=None):
    if folder is not None:
        shutil.rmtree(folder, ignore_errors=True)
    print(f'\n===  {_ok} passed, {_failed} failed  ===')
    sys.exit(1 if _failed else 0)
