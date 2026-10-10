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
# scales by two and has room left when GTK scales it to cover.
OVERSAMPLE = 2

# Enough for every cover in the rail and the open game's gallery several
# times over; beyond that the least recently used go.
CACHE_SIZE = 160

# (path, width) -> (mtime, texture or None), least recently used first.
_cache = OrderedDict()


def texture(path, width):
    '''A Gdk.Texture of the image at `path`, about `width` px wide, or None
    if it cannot be read as an image.'''
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
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(path), width * OVERSAMPLE, -1, True)
        result = Gdk.Texture.new_for_pixbuf(pixbuf)
    except GLib.Error:
        # A broken or not-an-image file: shown as the placeholder, never as
        # a crash.
        result = None
    _cache[key] = (mtime, result)
    _cache.move_to_end(key)
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return result
