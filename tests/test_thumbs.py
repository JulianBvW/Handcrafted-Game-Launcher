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

report(folder)
