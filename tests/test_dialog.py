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
from gi.repository import Adw  # noqa: E402

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
dialog._name.set_text('  Night Ferry ')
check('a name frees it', dialog._primary.get_sensitive())
dialog._description.get_buffer().set_text('Two strangers.')
dialog._version.set_text('0.3')
dialog._executable.set_text('~/Games/ferry/run.sh')
dialog._primary.emit('clicked')
ferry = window._selected
game = library.get(ferry)
check('saving adds the game', game is not None and game.name == 'Night Ferry',
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
      not window._body.get_can_focus())
window._dialog._on_cancel()
check('and gets it back afterwards', window._body.get_can_focus())
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
