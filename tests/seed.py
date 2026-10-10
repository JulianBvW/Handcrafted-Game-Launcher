'''Fill a throwaway library to look at the interface with.

    HOME=/tmp/hc-demo /usr/bin/python3 tests/seed.py [--with <launcher.sh>]
    HOME=/tmp/hc-demo /usr/bin/python3 -m handcrafted

Refuses to run unless HOME points into /tmp, so it can never write into a
real library. Nine games across all four statuses; the images are plain
coloured 16:9 panels drawn here, and the launchers are little scripts that
sleep, so Play and Stop can be tried without a single real game. --with
adds a real one on top.
'''

import os
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get('HOME', '')).resolve()
if not str(HOME).startswith('/tmp/'):
    sys.exit('seed.py: HOME must point into /tmp, e.g.\n'
             '    HOME=/tmp/hc-demo /usr/bin/python3 tests/seed.py')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gi  # noqa: E402

gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf  # noqa: E402

from handcrafted import config, images  # noqa: E402
from handcrafted.library import Library, totals  # noqa: E402

DAY = 86400
NOW = int(time.time())

# name, description, version, status, hours played, days since played
# (None: never), days since added, colours of its images
GAMES = [
    ('Kettle Summer', 'A seaside café, one long summer, and a kettle that '
     'is never quite off the boil. Short, warm, and kinder than it needs '
     'to be.',
     '1.2', 'playing', 23.7, 0, 40, ('#d9822b', '#6b3a1e', '#f2c14e')),
    ('The Leaf', 'Autumn in a village that forgets one thing every day.',
     'v0.9.3', 'playing', 4.2, 3, 21, ('#3f7d4e', '#a3b18a')),
    ('Night Ferry', 'Two strangers, one crossing, nine hours to talk.',
     '', 'playing', 11.0, 15, 70, ('#1d3557', '#457b9d', '#a8dadc',
                                   '#e63946')),
    ('Paper Lanterns', 'A festival town, a lost sister, and lanterns that '
     'remember who lit them.', '2.0.1', 'new', 0, None, 2,
     ('#9d4edd', '#e0aaff')),
    ('Glasshouse', 'Botany, grief, and a greenhouse that will not stay '
     'shut.', '1.0', 'new', 0, None, 9, ()),
    ('Salt Road', 'Caravans and contracts on a dried-up sea.', '1.4.2',
     'done', 17.5, 40, 120, ('#c9a227', '#7f5539', '#ddb892')),
    ('Long Division', 'A maths tutor and the one student who keeps '
     'getting the right answer the wrong way.', '', 'done', 6.3, 200, 300,
     ('#264653', '#2a9d8f')),
    ('Static', 'Late-night radio and a caller who knows too much.',
     '0.4', 'abandoned', 1.1, 400, 420, ('#3a3a40', '#8d99ae')),
    ('Missing Launcher', 'Its executable points nowhere, to show the '
     'error line.', '1.0', 'new', 0, None, 1, ('#e76f51',)),
]


def panel(path, colour, n):
    '''A 1600x900 image in one colour with a lighter band, so neighbouring
    images in the gallery can be told apart.'''
    value = int(colour[1:], 16)
    pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8,
                                  1600, 900)
    pixbuf.fill((value << 8) | 0xff)
    band = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8,
                                1600, 120)
    band.fill(0xffffff40 if n % 2 else 0x00000060)
    band.composite(pixbuf, 0, 600, 1600, 120, 0, 600, 1, 1,
                   GdkPixbuf.InterpType.NEAREST, 90)
    pixbuf.savev(str(path), 'png', [], [])


def main(argv):
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if config.LIBRARY_FILE.exists():
        sys.exit(f'seed.py: {config.LIBRARY_FILE} exists already; '
                 'use a fresh HOME')

    launchers = HOME / 'games'
    staging = HOME / 'panels'
    staging.mkdir(parents=True, exist_ok=True)
    library = Library()

    for (name, description, version, status, hours, played, added,
         colours) in GAMES:
        script = launchers / name.replace(' ', '_') / 'run.sh'
        if name != 'Missing Launcher':
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text('#!/bin/sh\nexec sleep 600\n')
            script.chmod(0o755)
        game = library.add(name, description, str(script), version,
                           now=NOW - added * DAY)
        library.set_status(game, status)
        if hours:
            session = library.start_session(
                game, now=NOW - (played or 0) * DAY)
            library.end_session(session, hours * 3600, 0)
            library.set_status(game, status)  # start_session moved new on

        sources = []
        for n, colour in enumerate(colours):
            path = staging / f'{game}-{n}.png'
            panel(path, colour, n)
            sources.append(path)
        images.replace(game, sources)

    if '--with' in argv:
        real = Path(argv[argv.index('--with') + 1]).expanduser().resolve()
        library.add(real.stem.replace('_', ' '), 'A real game.', str(real))

    count, seconds = totals(library.games())
    print(f'{count} games, {seconds // 3600}h played, '
          f'in {config.DATA_DIR}')
    library.close()


if __name__ == '__main__':
    main(sys.argv)
