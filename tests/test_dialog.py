'''The dialog for adding and editing games, worked without showing it.

    DISPLAY=:0 /usr/bin/python3 tests/test_dialog.py
'''

import os
import sys
from pathlib import Path

from harness import check, report, sandbox, section

if not os.environ.get('DISPLAY'):
    print('  SKIP  no DISPLAY; run as DISPLAY=:0 ... tests/test_dialog.py')
    sys.exit(0)

import gi  # noqa: E402

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from handcrafted import images  # noqa: E402
from handcrafted.library import Library  # noqa: E402
from handcrafted.window import HandcraftedWindow  # noqa: E402

folder = sandbox()
Adw.init()


class FakeLauncher:
    def __init__(self):
        self.running_game = None
        self._listeners = []

    def connect(self, callback):
        self._listeners.append(callback)

    def launch(self, game_id):
        self.running_game = game_id
        for callback in self._listeners:
            callback()

    def stop(self):
        self.running_game = None
        for callback in self._listeners:
            callback()


def texts(widget):
    found = [widget.get_label()] if isinstance(widget, Gtk.Label) else []
    child = widget.get_first_child()
    while child is not None:
        found.extend(texts(child))
        child = child.get_next_sibling()
    return found


def picture_files(contents):
    '''Files with the given bytes, to hand to images.replace().'''
    paths = []
    for n, content in enumerate(contents):
        path = folder / 'incoming' / f'{n}-{content.decode()}.png'
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(content)
        paths.append(path)
    return paths


def on_disk(game_id):
    return [path.read_bytes() for path in images.listing(game_id)]


library = Library()
T = 1_780_000_000
kettle = library.add('Kettle', 'Tea.', '/games/kettle-1.2/run.sh', '1.2',
                     now=T)
s = library.start_session(kettle, now=T + 100)
library.end_session(s, 5000, 0)
images.replace(kettle, picture_files([b'A', b'B', b'C']))

launcher = FakeLauncher()
window = HandcraftedWindow(library, launcher)

section('New game')

window.open_editor(None)
dialog = window._dialog
check('the dialog is open', dialog is not None)
check('the main button is greyed out without a name',
      not dialog._primary.get_sensitive())
dialog._name.set_text('   ')
check('and with only spaces', not dialog._primary.get_sensitive())
dialog._name.set_text('  Nine Hours Across ')
check('a name frees it', dialog._primary.get_sensitive())
dialog._description.get_buffer().set_text('Two strangers.')
dialog._version.set_text('0.3')
dialog._executable.set_text('~/Games/ferry/run.sh')
dialog._primary.emit('clicked')
ferry = window._selected
game = library.get(ferry)
check('saving adds the game', game is not None and game.name == 'Nine Hours Across',
      game)
check('with what was typed',
      (game.description, game.version) == ('Two strangers.', '0.3'), game)
check('~ in the path is expanded',
      game.executable == str(Path.home() / 'Games/ferry/run.sh'),
      game.executable)
check('the new game is selected', ferry != kettle)
check('the dialog is closed', window._dialog is None)
check('a new game is new', game.status == 'new')

section('Edit: the identity is the entry (DESIGN 2.2)')

before = library.get(kettle)
window.open_editor(kettle)
dialog = window._dialog
check('the fields are filled in',
      (dialog._name.get_text(), dialog._version.get_text())
      == ('Kettle', '1.2'))
dialog._executable.set_text('/games/kettle-1.3/run.sh')
dialog._version.set_text('1.3')
dialog._primary.emit('clicked')
after = library.get(kettle)
check('the new path is stored',
      after.executable == '/games/kettle-1.3/run.sh', after.executable)
check('playtime survives', after.playtime == before.playtime == 5000)
check('status survives', after.status == before.status)
check('added and last played survive',
      (after.added, after.last_played) == (before.added, before.last_played))
check('the images were not touched', on_disk(kettle) == [b'A', b'B', b'C'])

section('Images')

window.open_editor(kettle)
dialog = window._dialog
dialog._make_cover(2)
check('a click on the third makes it first in the dialog',
      [p.read_bytes() for p in dialog._pictures] == [b'C', b'A', b'B'])
check('but nothing on disk yet', on_disk(kettle) == [b'A', b'B', b'C'])
dialog._on_cancel()
check('Cancel leaves the disk alone', on_disk(kettle) == [b'A', b'B', b'C'])
check('and closes', window._dialog is None)

window.open_editor(kettle)
window._dialog._make_cover(2)
window._dialog._primary.emit('clicked')
check('saved, the third image is the cover',
      on_disk(kettle) == [b'C', b'A', b'B'], on_disk(kettle))
check('as 1.png', images.cover(kettle).name == '1.png')

window.open_editor(kettle)
window._dialog._remove(1)
window._dialog._primary.emit('clicked')
check('× removes one', on_disk(kettle) == [b'C', b'B'], on_disk(kettle))

section('While the dialog is open')

window.open_editor(kettle)
check('the library behind it takes no focus',
      not window._pages.get_can_focus())
window._dialog._on_cancel()
check('and gets it back afterwards', window._pages.get_can_focus())
window.open_editor(9999)
check('a game that is gone opens nothing, least of all "New game"',
      window._dialog is None)

window.open_editor(kettle)
gone = library.add('Doomed')
window._dialog_game = gone
library.delete(gone)
window._dialog._primary.emit('clicked')
check('saving a game deleted meanwhile closes instead of failing',
      window._dialog is None)

section('An image that cannot be copied')

count = len(library.games())
window.open_editor(None)
dialog = window._dialog
dialog._name.set_text('Broken Pictures')
dialog._pictures = [folder / 'incoming' / 'vanished.png']
dialog._primary.emit('clicked')
check('the dialog stays open and says why',
      window._dialog is dialog and dialog._error.get_visible()
      and 'Could not save the images' in dialog._error.get_label(),
      dialog._error.get_label())
dialog._primary.emit('clicked')
check('saving again does not add the game a second time',
      len(library.games()) == count + 1,
      [g.name for g in library.games()])
broken = window._dialog_game
dialog._pictures = []
dialog._pictures_changed = True
dialog._primary.emit('clicked')
check('and once the image is dropped, it saves and closes',
      window._dialog is None)
check('as the game it added the first time', window._selected == broken,
      (window._selected, broken))
library.delete(broken)
window.refresh()

section('Fix path…')

window.open_editor(kettle, focus='executable')
dialog = window._dialog
check('opens on the same game', dialog._name.get_text() == 'Kettle')
check('with the cursor going to the path field',
      dialog.first_focus is dialog._executable)
dialog._on_cancel()
window.open_editor(kettle)
check('the gear puts it in the name field',
      window._dialog.first_focus is window._dialog._name)
dialog = window._dialog
dialog._on_cancel()

section('Images from links')

from fakeweb import BASE, JPEG, PNG  # noqa: E402
from gi.repository import GLib  # noqa: E402


def until(condition, seconds=10):
    '''Run the main loop until `condition()` holds, as the app would.'''
    context = GLib.MainContext.default()
    deadline = GLib.get_monotonic_time() + seconds * 1_000_000
    while not condition() and GLib.get_monotonic_time() < deadline:
        context.iteration(False)
    return condition()


before = on_disk(kettle)
window.open_editor(kettle)
dialog = window._dialog
cache = window._dialog_folder
check('the dialog has a download folder of its own', cache.is_dir(), cache)
check('there is no link field in the dialog itself',
      not hasattr(dialog, '_links'))
check('but a plus tile at the end of the row',
      dialog._add is not None
      and dialog._thumbs.get_last_child().get_child() is dialog._add)
dialog.activate_action('dialog.from-url', None)
modal = dialog._modal
check('"From links…" opens the links sheet', modal is not None)
check('Load is greyed out while the field is empty',
      not modal._load.get_sensitive())
buffer = modal._links.get_buffer()
buffer.set_text(f'{BASE}/cover.png')
check('a link frees it', modal._load.get_sensitive())
buffer.set_text('')
buffer.insert_at_cursor('https://one.example/a.png')
modal._after_paste(buffer, None)
check('after pasting a link the cursor is on the next line',
      modal._link_text() == 'https://one.example/a.png\n',
      repr(modal._link_text()))
buffer.insert_at_cursor('https://two.example/b.png\n')
modal._after_paste(buffer, None)
check('a paste that ends in a newline gets no second one',
      modal._link_text().endswith('b.png\n'), repr(modal._link_text()))
buffer.set_text(f'{BASE}/cover.png\n\n{BASE}/missing.png\nnot a link\n'
                f'{BASE}/photo.jpg\n')
seen = set()
modal._load.connect('notify::label',
                    lambda button, _: seen.add(button.get_label()))
modal._load.emit('clicked')
check('and finishes', until(lambda: not modal.loading))
until(lambda: modal._load.get_label() == 'Load')
check('it counted along while loading',
      {'Loading 1/3…', 'Loading 2/3…', 'Loading 3/3…'} <= seen, seen)
check('two images are appended at the end',
      [p.read_bytes() for p in dialog._pictures] == before + [PNG, JPEG],
      len(dialog._pictures))
check('with failures the sheet stays open', dialog._modal is modal)
check('the failed and the refused lines stay in the field',
      modal._link_text().splitlines()
      == [f'{BASE}/missing.png', 'not a link'], modal._link_text())
check('with a summary', modal._load_summary.get_label() == '2 of 4 failed',
      modal._load_summary.get_label())
check('and a reason per line', len(texts(modal._load_reasons)) == 2
      and 'HTTP 404' in texts(modal._load_reasons)[0],
      texts(modal._load_reasons))
check('nothing in the library yet', on_disk(kettle) == before)
buffer.set_text(f'{BASE}/cover.png')
modal._load.emit('clicked')
check('all of them in, it closes by itself',
      until(lambda: dialog._modal is None))
dialog.activate_action('dialog.from-url', None)
modal = dialog._modal
modal._links.get_buffer().set_text(f'{BASE}/slow')
modal._start_loading()
dialog._on_key(None, Gdk.KEY_Escape, 0, 0)
check('Esc closes the sheet, not the dialog',
      dialog._modal is None and window._dialog is dialog)
check('and stops what was loading', not modal.loading)

section('Images from this computer')

mine = folder / 'mine'
mine.mkdir()
(mine / 'shot.png').write_bytes(PNG)
(mine / 'notes.png').write_text('not a picture')
count = len(dialog._pictures)
dialog.add_files([str(mine / 'shot.png'), str(mine / 'notes.png')])
check('the good file arrives at the end',
      until(lambda: len(dialog._pictures) == count + 1)
      and dialog._pictures[-1].read_bytes() == PNG)
check('as a copy in the dialog\'s folder, not the original',
      dialog._pictures[-1].parent == cache)
until(lambda: dialog._error.get_visible())
check('the bad one is named, with why',
      '1 of 2 could not be added' in dialog._error.get_label()
      and 'notes.png — could not be read as an image'
      in dialog._error.get_label(), dialog._error.get_label())
tile = dialog._add
dialog.add_files([str(mine / 'shot.png')])
dialog.add_files([str(mine / 'shot.png')])
check('a second batch while the first is copying does not cancel it',
      until(lambda: len(dialog._pictures) == count + 3), len(dialog._pictures))
check('the plus tile is the same one after images arrived, not rebuilt',
      dialog._add is tile
      and dialog._thumbs.get_last_child().get_child() is tile)
dialog.add_files([str(mine / 'shot.png')])
dialog._primary.emit('clicked')
check('Save pressed while a file is still copying waits for it',
      window._dialog is dialog and dialog._save_waiting
      or window._dialog is None)
check('and then saves with it',
      until(lambda: window._dialog is None)
      and len(on_disk(kettle)) == count + 4, len(on_disk(kettle)))
check('and the download folder is gone', not cache.exists())
before = on_disk(kettle)

window.open_editor(kettle)
dialog = window._dialog
dialog.activate_action('dialog.from-url', None)
check('behind the links sheet the form takes no focus',
      not dialog._content.get_can_focus())
dialog._close_links()
check('and gets it back afterwards', dialog._content.get_can_focus())
dialog._on_cancel()

window.open_editor(kettle)
dialog = window._dialog
cache = window._dialog_folder
dialog.activate_action('dialog.from-url', None)
dialog._modal._links.get_buffer().set_text(f'{BASE}/cover.png')
dialog._modal._load.emit('clicked')
until(lambda: dialog._modal is None)
check('loaded, waiting in the folder', any(cache.iterdir()))
dialog._on_cancel()
check('Cancel leaves the library alone', on_disk(kettle) == before)
check('and nothing in the download folder', not cache.exists())

from handcrafted import download  # noqa: E402


def no_room():
    raise OSError(28, 'No space left on device')


real_new_folder = download.new_folder
download.new_folder = no_room
window.open_editor(kettle)
check('with no room for a download folder there is no plus tile',
      window._dialog._add is None)
window._dialog._on_cancel()
download.new_folder = real_new_folder
section('Delete')

window.open_editor(None)
check('a new game has no Delete', window._dialog._delete is None)
window._dialog._on_cancel()

launcher.launch(kettle)
window.open_editor(kettle)
check('a running game cannot be deleted',
      not window._dialog._delete.get_sensitive())
launcher.stop()
check('and can once it has ended', window._dialog._delete.get_sensitive())

delete = window._dialog._delete
delete.emit('clicked')
launcher.launch(kettle)
launcher.stop()
check('starting the game in between takes the confirmation back',
      delete.get_label() == 'Delete game' and library.get(kettle))
delete.emit('clicked')
check('the first click only asks', library.get(kettle) is not None)
check('and says so', delete.get_label() == 'Click again to delete')
delete.emit('clicked')
check('the second deletes the game', library.get(kettle) is None)
check('and its images', not images.folder(kettle).exists())
check('the dialog is closed', window._dialog is None)
check('another game is selected', window._selected == ferry,
      (window._selected, ferry, [(g.id, g.name) for g in library.games()]))

window.close_now()
library.close()
report(folder)
