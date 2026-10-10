'''The settings file: whatever is in it, the program still starts.

    /usr/bin/python3 tests/test_config.py
'''

import json
from pathlib import Path

from harness import check, report, sandbox, section

from handcrafted import config

folder = sandbox()


def with_file(text):
    '''Write config.json as given and read it again.'''
    config.CONFIG_FILE.write_text(text, encoding='utf-8')
    config._apply_user_config()


def with_settings(settings):
    with_file(json.dumps(settings))


def at_defaults():
    return (config.WIDTH == config.DEFAULT_WIDTH
            and config.HEIGHT == config.DEFAULT_HEIGHT
            and config.DATA_DIR == config.DEFAULT_DATA_DIR
            and config.LANGUAGE is None)


section('Nothing usable in the file')

config.CONFIG_FILE.unlink(missing_ok=True)
config._apply_user_config()
check('no file leaves the defaults', at_defaults())

with_file('{"width": 1700,')
check('broken JSON leaves the defaults', at_defaults())

with_file('')
check('an empty file leaves the defaults', at_defaults())

with_settings([1700, 900])
check('a list instead of an object leaves the defaults', at_defaults())

with_settings({'colour': 'pink', 'zoom': 3})
check('unknown keys are ignored', at_defaults())

section('Size')

with_settings({'width': 1800, 'height': 1000})
check('a valid size is taken', (config.WIDTH, config.HEIGHT) == (1800, 1000),
      f'{config.WIDTH} x {config.HEIGHT}')

with_settings({'width': True})
check('true is not a width', config.WIDTH == config.DEFAULT_WIDTH,
      str(config.WIDTH))

with_settings({'width': '1700'})
check('a string is not a width', config.WIDTH == config.DEFAULT_WIDTH,
      str(config.WIDTH))

with_settings({'width': 1700.5})
check('a float is not a width', config.WIDTH == config.DEFAULT_WIDTH,
      str(config.WIDTH))

with_settings({'width': 200, 'height': -5})
check('too small is raised to the minimum',
      (config.WIDTH, config.HEIGHT) == (config.MIN_WIDTH, config.MIN_HEIGHT),
      f'{config.WIDTH} x {config.HEIGHT}')

section('Data folder')

with_settings({'data_dir': '~/Somewhere/Else'})
expected = Path.home() / 'Somewhere' / 'Else'
check('~ is expanded', config.DATA_DIR == expected, str(config.DATA_DIR))
check('the library follows the data folder',
      config.LIBRARY_FILE == expected / 'library.db', str(config.LIBRARY_FILE))
check('the images follow the data folder',
      config.IMAGES_DIR == expected / 'images', str(config.IMAGES_DIR))

with_settings({'data_dir': '   '})
check('a blank folder is ignored', at_defaults(), str(config.DATA_DIR))

with_settings({'data_dir': 42})
check('a number is not a folder', at_defaults(), str(config.DATA_DIR))

with_settings({'data_dir': 'testlib'})
check('a relative folder is ignored', at_defaults(), str(config.DATA_DIR))

with_settings({'data_dir': '~nobody-by-this-name/lib'})
check('~ of an unknown user is ignored, not raised', at_defaults(),
      str(config.DATA_DIR))

section('Language')

with_settings({})
check('no language follows the system', config.LANGUAGE is None)
for code in ('de', 'en', 'de_DE', 'fil'):
    with_settings({'language': code})
    check(f'{code} is a language', config.LANGUAGE == code,
          repr(config.LANGUAGE))
for code in ('German', 'DE', 'de-DE', '../etc', '', 'd', True, ['de']):
    with_settings({'language': code})
    check(f'{code!r} is not a language', config.LANGUAGE is None,
          repr(config.LANGUAGE))

section('Pathological JSON')

with_file('[' * 100000 + ']' * 100000)
check('nesting deep enough to exhaust recursion is not raised',
      at_defaults())

section('Reading twice')

with_settings({'width': 1800, 'data_dir': '/tmp/x'})
config.CONFIG_FILE.unlink()
config._apply_user_config()
check('a removed file returns everything to the defaults', at_defaults())
check('including the derived paths',
      config.LIBRARY_FILE == config.DEFAULT_DATA_DIR / 'library.db',
      str(config.LIBRARY_FILE))

report(folder)
