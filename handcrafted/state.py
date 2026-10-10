'''What the window remembers between sessions: how big it was.

Only the size and whether it was maximized. GTK 4 can neither read nor set
a window's position on X11, so where the window opens is left to the window
manager.

Free of GTK, so the rules can be checked without a display.
'''

import json

from . import config


def defaults():
    '''The window as it opens before it has ever been resized.'''
    return {'width': config.WIDTH, 'height': config.HEIGHT,
            'maximized': False}


def load():
    '''The remembered size, or the defaults for anything doubtful.

    Deliberately suspicious. A missing file, half-written JSON, a string
    where a number belongs, a width of four pixels -- every one of those
    falls back to a sane value rather than raising.
    '''
    state = defaults()
    try:
        stored = json.loads(config.STATE_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError, RecursionError):
        return state
    if not isinstance(stored, dict):
        return state

    for key in ('width', 'height'):
        value = stored.get(key)
        # bool is an int as far as Python is concerned, and not one we want.
        if isinstance(value, int) and not isinstance(value, bool):
            state[key] = value

    if isinstance(stored.get('maximized'), bool):
        state['maximized'] = stored['maximized']

    state['width'] = max(config.MIN_WIDTH, state['width'])
    state['height'] = max(config.MIN_HEIGHT, state['height'])
    return state


def save(width, height, maximized):
    '''Write the size, or quietly give up.

    Through a neighbouring file and a rename, so that dying mid-write leaves
    the previous version intact instead of half a file.
    '''
    path = config.STATE_FILE
    scratch = path.with_suffix(path.suffix + '.tmp')
    data = {'width': width, 'height': height, 'maximized': maximized}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        scratch.write_text(json.dumps(data, indent=2) + '\n',
                           encoding='utf-8')
        scratch.replace(path)
    except OSError:
        # Not being able to remember the window size is not worth a crash.
        pass
