'''A game's images on disk.

    /usr/bin/python3 tests/test_images.py
'''

import os
import time

from harness import check, report, sandbox, section

from handcrafted import config, images

folder = sandbox()
incoming = folder / 'incoming'
incoming.mkdir()


def made(name, content):
    path = incoming / name
    path.write_bytes(content)
    return path


def contents(game_id):
    return [path.read_bytes() for path in images.listing(game_id)]


def names(game_id):
    return [path.name for path in images.listing(game_id)]


section('Nothing there yet')

check('no folder is no images', images.listing(1) == [])
check('and no cover', images.cover(1) is None)

section('Replacing')

images.replace(1, [made('a.png', b'A'), made('b.JPG', b'B'),
                   made('c.webp', b'C')])
check('numbered from 1, extension kept and lowered',
      names(1) == ['1.png', '2.jpg', '3.webp'], names(1))
check('the content is copied', contents(1) == [b'A', b'B', b'C'])
check('the first is the cover', images.cover(1).name == '1.png')
check('the sources stay where they were', (incoming / 'a.png').exists())

current = images.listing(1)
images.replace(1, [current[2], current[0], current[1]])
check('the third becomes the cover', contents(1) == [b'C', b'A', b'B'],
      contents(1))
check('and the files are renamed to match',
      names(1) == ['1.webp', '2.png', '3.jpg'], names(1))

current = images.listing(1)
images.replace(1, [current[0], current[2], made('d.png', b'D')])
check('removing one and appending another',
      contents(1) == [b'C', b'B', b'D'], contents(1))

images.replace(1, [])
check('an empty list removes the folder', not images.folder(1).exists())

section('Order')

images.replace(2, [made(f'{n}.png', bytes([n])) for n in range(1, 12)])
check('10 comes after 9', names(2)[8:11] == ['9.png', '10.png', '11.png'],
      names(2))
(images.folder(2) / 'notes.txt').write_text('x')
(images.folder(2) / 'cover.png').write_bytes(b'x')
(images.folder(2) / '\u00b2.png').write_bytes(b'x')
check('files not named by a number are ignored', len(names(2)) == 11,
      names(2))

section('Interrupted')

images.replace(3, [made('x.png', b'X')])
staging = config.IMAGES_DIR / '.3.new'
staging.mkdir()
(staging / '1.png').write_bytes(b'half')
images.replace(3, [made('y.png', b'Y'), *images.listing(3)])
check('a half-built staging folder is cleared',
      contents(3) == [b'Y', b'X'], contents(3))
check('and nothing is left beside it', not staging.exists())

# Died between the two renames: the old set retired, the new set whole.
images.folder(3).rename(config.IMAGES_DIR / '.3.old')
(config.IMAGES_DIR / '.3.new').mkdir()
(config.IMAGES_DIR / '.3.new' / '1.png').write_bytes(b'NEW')
check('the finished new set is taken', contents(3) == [b'NEW'], contents(3))
check('and the retired one cleared',
      not (config.IMAGES_DIR / '.3.old').exists())

# Died with only the retired folder left: it goes back.
images.folder(3).rename(config.IMAGES_DIR / '.3.old')
check('the retired set comes back if nothing replaced it',
      contents(3) == [b'NEW'], contents(3))

section('Kept listings')

images.replace(5, [made('k1.png', b'K1'), made('k2.png', b'K2')])
check('a folder changed just now is not kept: its mtime is too coarse',
      str(images.folder(5)) not in images._listings)
# As if it had been written a minute ago.
a_minute_ago = time.time_ns() - 60_000_000_000
os.utime(images.folder(5), ns=(a_minute_ago, a_minute_ago))
first = images.listing(5)
check('an older one is', str(images.folder(5)) in images._listings)
second = images.listing(5)
check('asked again, the same answer', first == second)
second.clear()
check('and handing it out does not let it be changed',
      len(images.listing(5)) == 2)
(images.folder(5) / '3.png').write_bytes(b'K3')
check('a file added by hand is still seen', names(5) == ['1.png', '2.png',
                                                         '3.png'], names(5))
(images.folder(5) / '3.png').unlink()
check('and one taken away', names(5) == ['1.png', '2.png'], names(5))
before = images.generation
images.replace(5, [made('k3.png', b'K3')])
check('a replace is counted, so views know to draw again',
      images.generation == before + 1)
check('and listed anew', contents(5) == [b'K3'], contents(5))
images.remove(5)
check('so is a remove', images.generation == before + 2)
check('after which nothing is listed', images.listing(5) == [])

section('Removing')

images.remove(2)
check('remove takes the folder', not images.folder(2).exists())
images.replace(4, [made('z.png', b'Z')])
(config.IMAGES_DIR / '.4.new').mkdir()
(config.IMAGES_DIR / '.4.old').mkdir()
images.remove(4)
check('remove also takes what an interrupted replace left',
      not any(config.IMAGES_DIR.glob('*4*')),
      [p.name for p in config.IMAGES_DIR.iterdir()])
images.remove(99)
check('removing what is not there is no error', True)

report(folder)
