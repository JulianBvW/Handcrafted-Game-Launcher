'''A game's images on disk: images/<game_id>/<n>.<ext>, n counting from 1.

The folder is the truth about which images a game has and in what order;
the database does not keep a second list that could disagree with it.
1.<ext> is always the cover.

Free of GTK.
'''

import shutil
import time
from pathlib import Path

from . import config


def folder(game_id):
    return config.IMAGES_DIR / str(game_id)


def _recover(game_id):
    '''Finish a replace() that died between its two renames.

    The old folder is only retired once the new one is completely copied,
    so a retired folder without a current one means the staging folder is
    whole and only needs its last rename. If that is gone too, the retired
    folder goes back. Without a retired folder the staging folder may be
    half-copied, and is left for replace() to clear.
    '''
    target = folder(game_id)
    staging = target.with_name(f'.{game_id}.new')
    retired = target.with_name(f'.{game_id}.old')
    if retired.exists() and not target.exists():
        (staging if staging.exists() else retired).rename(target)
    if target.exists():
        shutil.rmtree(retired, ignore_errors=True)


# str(folder) -> ((inode, mtime), [Path, ...]). A folder's mtime changes
# whenever a file in it is added, removed or renamed, and replace() swaps in
# a new folder altogether, so one stat tells whether a listing still holds.
_listings = {}

# Counts every replace() and remove(). After a replace the files may have
# the very same names with other pictures in them; views compare this to
# know they have to draw again.
generation = 0


def listing(game_id):
    '''The images in order. Only files named by a number count, sorted as
    numbers so 10.jpg comes after 9.jpg.

    Asked for every game in the rail on every redraw, so it is kept: as
    long as the folder is unchanged, one stat instead of reading it.'''
    target = folder(game_id)
    key = str(target)
    try:
        info = target.stat()
    except OSError:
        info = None
    if info is not None:
        stamp = (info.st_ino, info.st_mtime_ns)
        cached = _listings.get(key)
        if cached is not None and cached[0] == stamp:
            return list(cached[1])

    # Not known, or changed: only now look for what a crash left behind.
    _recover(game_id)
    try:
        info = target.stat()
        entries = list(target.iterdir())
    except OSError:
        _listings.pop(key, None)
        return []
    numbered = [path for path in entries
                # isdigit() alone also takes '²', which int() cannot read.
                if path.is_file() and path.stem.isascii()
                and path.stem.isdigit()]
    numbered.sort(key=lambda path: int(path.stem))
    # Not kept while the folder is fresh: its mtime only moves in coarse
    # ticks, and a file added within the same tick would go unseen. (Git
    # does the same with what it calls racily clean entries.)
    if time.time_ns() - info.st_mtime_ns > 2_000_000_000:
        _listings[key] = ((info.st_ino, info.st_mtime_ns), numbered)
    else:
        _listings.pop(key, None)
    return list(numbered)


def stamp(paths):
    '''What a view drew from `paths` (image files, or None for none), in a
    form it can compare with next time: each file with its mtime, so a
    picture saved over another under the same name counts as a change, and
    the generation, so one replaced within the same clock tick does too.'''
    stamped = []
    for path in paths:
        try:
            mtime = path.stat().st_mtime_ns if path is not None else None
        except OSError:
            mtime = None
        stamped.append((path, mtime))
    return generation, tuple(stamped)


def cover(game_id):
    images = listing(game_id)
    return images[0] if images else None


def replace(game_id, sources):
    '''Make `sources`, in this order, the game's images.

    The one way of writing. Reordering, removing, appending freshly loaded
    images and making one the cover are all a new list passed in here.
    Sources may be the game's own current images or files from anywhere
    else, such as the download cache.

    Built in a neighbouring folder and swapped in by renaming, so a run that
    dies halfway leaves either the old set or the new one, never a mixture.
    '''
    global generation
    generation += 1
    sources = [Path(source) for source in sources]
    target = folder(game_id)
    staging = target.with_name(f'.{game_id}.new')
    retired = target.with_name(f'.{game_id}.old')

    # Leftovers of a run that died in here: finished if it can be, thrown
    # away if not. Before the sources are read, since they may point into
    # the folder being recovered.
    _recover(game_id)
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(retired, ignore_errors=True)

    if not sources:
        shutil.rmtree(target, ignore_errors=True)
        return

    # Copied rather than moved: a source may be one of the very files the
    # old folder is about to be retired with.
    staging.mkdir(parents=True)
    for n, source in enumerate(sources, start=1):
        shutil.copyfile(source, staging / f'{n}{source.suffix.lower()}')

    if target.exists():
        target.rename(retired)
    staging.rename(target)
    shutil.rmtree(retired, ignore_errors=True)


def remove(game_id):
    '''All of a game's images, for when the game itself is deleted.

    Including what an interrupted replace() may have left beside them: ids
    are never handed out again, so nothing else would ever clear it.
    '''
    global generation
    generation += 1
    target = folder(game_id)
    for path in (target, target.with_name(f'.{game_id}.new'),
                 target.with_name(f'.{game_id}.old')):
        shutil.rmtree(path, ignore_errors=True)
