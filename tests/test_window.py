'''The library view, built and worked without showing it.

    DISPLAY=:0 /usr/bin/python3 tests/test_window.py

Needs a display, since GTK will not build a widget without one. Uses a
library of its own and a stand-in launcher, so no game is ever started.
'''

import os
import sys

from harness import check, report, sandbox, section

if not os.environ.get('DISPLAY'):
    print('  SKIP  no DISPLAY; run as DISPLAY=:0 ... tests/test_window.py')
    sys.exit(0)

import gi  # noqa: E402

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from handcrafted import images  # noqa: E402
from handcrafted.launch import LaunchError  # noqa: E402
from handcrafted.library import Library  # noqa: E402
from handcrafted.window import HandcraftedWindow  # noqa: E402

folder = sandbox()
Adw.init()


class FakeLauncher:
    '''Launcher's interface, without processes.'''

    def __init__(self):
        self.running_game = None
        self._listeners = []
        self.refuse = {}  # game_id -> reason launch() fails with

    def connect(self, callback):
        self._listeners.append(callback)

    def launch(self, game_id):
        if game_id in self.refuse:
            raise LaunchError(self.refuse[game_id])
        self.running_game = game_id
        for callback in self._listeners:
            callback()

    def stop(self):
        self.running_game = None
        for callback in self._listeners:
            callback()


def texts(widget):
    '''Every label's text under `widget`, in tree order.'''
    found = []
    if isinstance(widget, Gtk.Label):
        found.append(widget.get_label())
    child = widget.get_first_child()
    while child is not None:
        found.extend(texts(child))
        child = child.get_next_sibling()
    return found


def find(widget, kind):
    if isinstance(widget, kind):
        return widget
    child = widget.get_first_child()
    while child is not None:
        hit = find(child, kind)
        if hit is not None:
            return hit
        child = child.get_next_sibling()
    return None


def launcher_file(name):
    path = folder / 'games' / name / 'run.sh'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/bin/sh\nexit 0\n')
    path.chmod(0o755)
    return str(path)


library = Library()
T = 1_780_000_000
alpha = library.add('Alpha', 'First.', launcher_file('alpha'), '1.0',
                    now=T)
beta = library.add('The Beta', 'Second.', launcher_file('beta'), now=T + 10)
gamma = library.add('Gamma', 'Third.', str(folder / 'gone.sh'), now=T + 20)
s = library.start_session(alpha, now=T + 100)
library.end_session(s, 7200, 0)

launcher = FakeLauncher()
window = HandcraftedWindow(library, launcher)
rail = window._rail
detail = window._detail

section('First look')

rail_text = texts(rail)
check('the head shows count and total time', '3 · 2h 0m' in rail_text,
      rail_text[:4])
heads = [t for t in rail_text if t in ('NEW', 'PLAYING', 'DONE',
                                       'ABANDONED')]
check('groups in the order New, Playing', heads == ['NEW', 'PLAYING'],
      heads)
check('the most recently active game is selected first',
      window._selected == alpha, window._selected)
check('the detail shows it', 'Alpha' in texts(detail))

section('Selecting')

window.select(beta)
shown = texts(detail)
check('a selection changes the title', 'The Beta' in shown)
check('and the figures', 'Never' in shown and '0h' in shown, shown)
check('a game without images shows the placeholder', 'no images' in shown)
check('and its rail row a placeholder initial, skipping "The"',
      'B' in texts(rail))

window.select(gamma)
shown = texts(detail)
check('a missing launcher shows the error line',
      'Executable not found' in shown, shown)
play = find(detail, Gtk.Button)
check('and Play is greyed out', not play.get_sensitive())

plain = folder / 'games' / 'plain' / 'run.sh'
plain.parent.mkdir(parents=True)
plain.write_text('#!/bin/sh\nexit 0\n')
plain.chmod(0o644)
library.update(gamma, executable=str(plain))
window.refresh()
shown = texts(detail)
check('a launcher without the x bit says so, not "not found"',
      'Executable is not marked as runnable' in shown, shown)
library.update(gamma, executable=str(folder / 'gone.sh'))

section('A start that fails anyway')

window.select(beta)
launcher.refuse[beta] = 'Exec format error'
window._on_play(beta)
shown = texts(detail)
check('the reason is shown instead of nothing happening',
      'Could not start: Exec format error' in shown, shown)
window.select(alpha)
window.select(beta)
check('and is gone once another game was selected',
      not any(t.startswith('Could not start') for t in texts(detail)))
del launcher.refuse[beta]

section('Status')

window.select(beta)
window.activate_action('win.status', GLib.Variant('s', 'done'))
check('the menu sets the status in the library',
      library.get(beta).status == 'done')
# The redraw waits until the menu has closed; let the main loop run it.
context = GLib.MainContext.default()
while context.pending():
    context.iteration(False)
heads = [t for t in texts(rail) if t in ('NEW', 'PLAYING', 'DONE')]
check('and the rail regroups', heads == ['NEW', 'PLAYING', 'DONE'], heads)

section('Running')

window.select(alpha)
window._on_play(alpha)
check('Play starts the game', launcher.running_game == alpha)
check('its own button reads Running · Stop',
      'Running · Stop' in texts(detail))
window.select(beta)
play = find(detail, Gtk.Button)
check('another game\'s Play is greyed out', not play.get_sensitive())
check('with the reason as tooltip',
      play.get_tooltip_text() == 'Another game is running')
window.select(alpha)
window._on_play(alpha)
check('Play on the running game stops it', launcher.running_game is None)

section('Now playing')

rail._playing.set_active(True)
heads = [t for t in texts(rail) if t in ('NEW', 'PLAYING', 'DONE')]
check('only the playing group is left', heads == ['PLAYING'], heads)
check('the switch counts them', 'Now playing · 1' in texts(rail))
rail._everything.set_active(True)
check('and Everything brings the rest back',
      'Now playing' in texts(rail) and 'NEW' in texts(rail))

section('Deleted underneath')

images.remove(alpha)
library.delete(alpha)
window.refresh()
check('a selection that is gone moves to another game',
      window._selected in (beta, gamma), window._selected)

section('Empty')

for game in library.games():
    library.delete(game.id)
window.refresh()
check('an empty library says so',
      'Your library is empty' in texts(detail))
check('with totals of nothing', '0 · 0h' in texts(rail))

window.close_now()
library.close()
report(folder)
