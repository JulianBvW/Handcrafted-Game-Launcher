'''Constants and paths, all in one place.

Everything here is a default. A few of them can be overridden in
`~/.config/handcrafted/config.json`, which is read at the bottom of this
file. A file is not a settings window, so that non-goal stands.
'''

import json
import re
from pathlib import Path

# D-Bus name. A second start finds the running instance by it and hands over
# to that one instead of opening another window.
APP_ID = 'io.github.julianbvw.Handcrafted'

# Instance part of WM_CLASS, and the name the desktop shows for the process.
PRG_NAME = 'handcrafted'
APP_NAME = 'Handcrafted'

# 16:9, the shape every image comes in, and comfortably under the 1080 px of
# the screen it was drawn for. Only a starting value: the size the window was
# left at is remembered in state.json.
DEFAULT_WIDTH = 1600
DEFAULT_HEIGHT = 900
WIDTH = DEFAULT_WIDTH
HEIGHT = DEFAULT_HEIGHT

# Below this the two-column library no longer fits.
MIN_WIDTH = 1280
MIN_HEIGHT = 720

CONFIG_DIR = Path.home() / '.config' / 'handcrafted'
CONFIG_FILE = CONFIG_DIR / 'config.json'
STATE_FILE = CONFIG_DIR / 'state.json'

# Images being loaded from a link list wait here until the dialog is saved,
# so cancelling leaves nothing behind in the library.
CACHE_DIR = Path.home() / '.cache' / 'handcrafted'

# The library itself. data_dir in config.json moves all of it at once, which
# is what lets a test library sit next to the real one without touching it.
DEFAULT_DATA_DIR = Path.home() / '.local' / 'share' / 'handcrafted'
DATA_DIR = DEFAULT_DATA_DIR
LIBRARY_FILE = DATA_DIR / 'library.db'
IMAGES_DIR = DATA_DIR / 'images'

# The interface language: a code such as 'de' or 'de_DE'. None follows the
# system. English needs no catalogue and is what anything untranslated
# falls back to.
LANGUAGE = None
LANGUAGE_PATTERN = re.compile(r'[a-z]{2,3}(_[A-Z]{2})?')

# The stylesheet ships next to the code.
STYLE_FILE = Path(__file__).resolve().parent / 'style.css'


def _apply_user_config():
    '''Let config.json override the few defaults that can be overridden.

    Suspicious on purpose: a program that will not start because of its
    settings file is worse than one running with the wrong settings. Anything
    missing, unreadable, malformed or of the wrong type leaves the default
    standing, and keys it does not know are ignored.

    Starts from the defaults every time, so calling it twice gives the same
    result as calling it once -- the tests rely on that.
    '''
    global WIDTH, HEIGHT, DATA_DIR, LIBRARY_FILE, IMAGES_DIR, LANGUAGE

    WIDTH, HEIGHT, DATA_DIR = DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_DATA_DIR
    LANGUAGE = None

    try:
        settings = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError, RecursionError):
        # RecursionError: thousands of nested brackets are still not JSON
        # worth dying for.
        settings = {}
    if not isinstance(settings, dict):
        settings = {}

    width = settings.get('width')
    # bool is an int to Python, and not one we want here.
    if isinstance(width, int) and not isinstance(width, bool):
        WIDTH = max(MIN_WIDTH, width)

    height = settings.get('height')
    if isinstance(height, int) and not isinstance(height, bool):
        HEIGHT = max(MIN_HEIGHT, height)

    folder = settings.get('data_dir')
    if isinstance(folder, str) and folder.strip():
        try:
            # Raises for ~someone whose home cannot be found.
            folder = Path(folder.strip()).expanduser()
        except RuntimeError:
            folder = None
        # A relative path would put the library wherever the program happened
        # to be started from -- the same file, two different libraries.
        if folder is not None and folder.is_absolute():
            DATA_DIR = folder

    language = settings.get('language')
    if isinstance(language, str) and LANGUAGE_PATTERN.fullmatch(language):
        LANGUAGE = language

    # Derived last, so a moved data_dir takes everything under it along.
    LIBRARY_FILE = DATA_DIR / 'library.db'
    IMAGES_DIR = DATA_DIR / 'images'


_apply_user_config()
