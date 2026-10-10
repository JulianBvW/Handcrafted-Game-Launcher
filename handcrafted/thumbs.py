'''Images, read at the size they are shown at, and kept.

A cover in the rail is 104 px wide; the file behind it may be 4000. Reading
every image at full size whenever the rail is rebuilt would cost seconds
with twenty games, so each is decoded once at (twice) the width it is shown
at and the texture kept for as long as the file stays the same.
'''

from collections import OrderedDict

import gi

gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, GLib  # noqa: E402

# Twice the width on screen, so the picture stays sharp when the desktop
# scales by two and has room left when GTK scales it to cover. Never more
# than the file itself has: enlarging only costs memory.
OVERSAMPLE = 2

# The width for pictures that fill a window: the hero and the detail
# column's backdrop share it, so the cover behind both is decoded once.
LARGE = 1280

# Kept by size, not by count: one window-wide cover weighs as much as a
# hundred rail thumbnails. Beyond this the least recently used go.
BUDGET = 256 * 1024 * 1024

# (path, width) -> (mtime, texture or None, bytes), least recently used
# first.
_cache = OrderedDict()
_used = 0


def texture(path, width):
    '''A Gdk.Texture of the image at `path`, about `width` px wide, or None
    if it cannot be read as an image.'''
    global _used
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
    key = (str(path), width)
    cached = _cache.get(key)
    if cached is not None and cached[0] == mtime:
        _cache.move_to_end(key)
        return cached[1]

    # New, or the file changed since: one entry per file and width, so a
    # replaced image pushes its old texture out rather than piling up.
    try:
        target = width * OVERSAMPLE
        _info, original, _height = GdkPixbuf.Pixbuf.get_file_info(str(path))
        if original:
            target = min(target, original)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(path), target, -1, True)
        result = Gdk.Texture.new_for_pixbuf(pixbuf)
        size = pixbuf.get_width() * pixbuf.get_height() * 4
    except GLib.Error:
        # A broken or not-an-image file: shown as the placeholder, never as
        # a crash.
        result, size = None, 0
    if cached is not None:
        _used -= cached[2]
    _cache[key] = (mtime, result, size)
    _cache.move_to_end(key)
    _used += size
    while _used > BUDGET and len(_cache) > 1:
        _key, (_mtime, _texture, dropped) = _cache.popitem(last=False)
        _used -= dropped
    return result
