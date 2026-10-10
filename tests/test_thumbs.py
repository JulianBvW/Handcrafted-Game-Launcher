'''Images read at the size they are shown at, and kept.

    /usr/bin/python3 tests/test_thumbs.py
'''

import gi

from harness import check, report, sandbox, section

gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf  # noqa: E402

from handcrafted import thumbs  # noqa: E402

folder = sandbox()


def image(name, width, height):
    path = folder / f'{name}.png'
    GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, width,
                         height).savev(str(path), 'png', [], [])
    return path


section('Size')

big = image('big', 1600, 900)
texture = thumbs.texture(big, 104)
check('read at twice the width it is shown at',
      texture.get_width() == 208, texture.get_width())
small = image('small', 320, 180)
texture = thumbs.texture(small, thumbs.LARGE)
check('but never larger than the file itself',
      texture.get_width() == 320, texture.get_width())

section('Kept')

check('asked again, the same texture', thumbs.texture(big, 104)
      is thumbs.texture(big, 104))
broken = folder / 'broken.png'
broken.write_bytes(b'not a picture')
check('a file that is no image gives none', thumbs.texture(broken, 104)
      is None)
check('a file that is not there gives none',
      thumbs.texture(folder / 'gone.png', 104) is None)

section('Within budget')

thumbs.BUDGET = 3 * 208 * 117 * 4
paths = [image(f'n{n}', 1600, 900) for n in range(5)]
for path in paths:
    thumbs.texture(path, 104)
check('the least recently used go once it is full',
      thumbs._used <= thumbs.BUDGET
      and str(paths[0]) not in {key[0] for key in thumbs._cache},
      (thumbs._used, len(thumbs._cache)))
check('the most recent stay',
      (str(paths[-1]), 104) in thumbs._cache)
huge = image('huge', 1600, 900)
check('one larger than the whole budget is still handed out',
      thumbs.texture(huge, thumbs.LARGE) is not None)

section('Moving pictures')

import time  # noqa: E402

# A 1 x 1 GIF of two frames, a tenth of a second each, looping: written out
# by hand, since GdkPixbuf reads GIFs but does not write them.
GIF = bytes.fromhex(
    '474946383961' '0100' '0100' '80' '00' '00'   # header, screen, 2 colours
    '000000' 'ffffff'                                # black, white
    '21ff0b' + b'NETSCAPE2.0'.hex() + '03010000' '00'  # loop for ever
    '21f904' '000a00' '00' '00'                      # 10/100 s
    '2c' '00000000' '0100' '0100' '00'               # one frame, 1 x 1
    '02' '02' '4401' '00'                            # pixel 0
    '21f904' '000a00' '00' '00'
    '2c' '00000000' '0100' '0100' '00'
    '02' '02' '4c01' '00'                            # pixel 1
    '3b')
moving = folder / 'moving.gif'
moving.write_bytes(GIF)
playing = thumbs.animation(moving)
check('an animated GIF plays', playing is not None)
check('at its own size', (playing.get_intrinsic_width(),
                          playing.get_intrinsic_height()) == (1, 1))
first = playing._texture
time.sleep(0.15)
playing._next()
check('and moves on to its next frame', playing._texture is not first)
check('a still image is not an animation', thumbs.animation(big) is None)

report(folder)
