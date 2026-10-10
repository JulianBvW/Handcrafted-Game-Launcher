'''The remembered window size: written atomically, read suspiciously.

    /usr/bin/python3 tests/test_state.py
'''

import json
import os

from harness import check, report, sandbox, section

from handcrafted import config, state

folder = sandbox()


def stored(text):
    config.STATE_FILE.write_text(text, encoding='utf-8')
    return state.load()


section('Nothing usable in the file')

config.STATE_FILE.unlink(missing_ok=True)
check('no file gives the defaults', state.load() == state.defaults())
check('broken JSON gives the defaults',
      stored('{"width": 1700') == state.defaults())
check('a list gives the defaults', stored('[1, 2]') == state.defaults())

section('Values')

loaded = stored(json.dumps({'width': 1700, 'height': 950,
                            'maximized': True, 'selected': 7,
                            'hero': 4}))
check('a valid state is taken',
      loaded == {'width': 1700, 'height': 950, 'maximized': True,
                 'selected': 7, 'hero': 4}, loaded)

loaded = stored(json.dumps({'selected': True}))
check('true is not a game', loaded['selected'] is None, loaded)
loaded = stored(json.dumps({'selected': '7'}))
check('a string is not a game', loaded['selected'] is None, loaded)
loaded = stored(json.dumps({'hero': 'Kettle'}))
check('nor is it a hero', loaded['hero'] is None, loaded)

loaded = stored(json.dumps({'width': True, 'height': '900'}))
check('bools and strings are not sizes',
      (loaded['width'], loaded['height']) == (config.WIDTH, config.HEIGHT),
      loaded)

loaded = stored(json.dumps({'maximized': 1}))
check('1 is not a bool', loaded['maximized'] is False, loaded)

loaded = stored(json.dumps({'width': 4, 'height': 4}))
check('too small is raised to the minimum',
      (loaded['width'], loaded['height'])
      == (config.MIN_WIDTH, config.MIN_HEIGHT), loaded)

loaded = stored(json.dumps({'width': 1500, 'x': 10, 'y': 20}))
check('position keys from elsewhere are ignored',
      set(loaded) == {'width', 'height', 'maximized', 'selected', 'hero'},
      loaded)

section('Round trip')

state.save({'width': 1440, 'height': 810, 'maximized': False,
            'selected': 3, 'hero': 5})
check('what was saved comes back',
      state.load() == {'width': 1440, 'height': 810, 'maximized': False,
                       'selected': 3, 'hero': 5})
check('no scratch file is left behind',
      not config.STATE_FILE.with_suffix('.json.tmp').exists())

state.save({'width': 1440, 'height': 810, 'maximized': True,
            'selected': None, 'stray': 'x'})
check('maximized comes back', state.load()['maximized'] is True)
check('no selection comes back as none', state.load()['selected'] is None)
check('keys that are not state are not written',
      'stray' not in json.loads(config.STATE_FILE.read_text()))

loaded = stored('[' * 100000 + ']' * 100000)
check('nesting deep enough to exhaust recursion gives the defaults',
      loaded == state.defaults())

section('Cannot write')

# root writes into a read-only folder regardless, so the check means nothing
# there.
if os.geteuid() == 0:
    print('  SKIP  running as root')
else:
    config.STATE_FILE.unlink()
    os.chmod(folder, 0o500)
    try:
        state.save(state.defaults())
        check('a read-only folder does not raise', True)
    finally:
        os.chmod(folder, 0o700)
    check('and nothing was written', not config.STATE_FILE.exists())

report(folder)
