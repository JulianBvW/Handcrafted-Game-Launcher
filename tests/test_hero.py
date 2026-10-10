'''The hero, built and worked without showing it.

    DISPLAY=:0 /usr/bin/python3 tests/test_hero.py
'''

import os
import sys

from harness import check, report, sandbox, section

if not os.environ.get('DISPLAY'):
    print('  SKIP  no DISPLAY; run as DISPLAY=:0 ... tests/test_hero.py')
    sys.exit(0)

import gi  # noqa: E402

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk  # noqa: E402

from handcrafted import images, state  # noqa: E402
from handcrafted.launch import LaunchError  # noqa: E402
from handcrafted.library import Library  # noqa: E402
from handcrafted.widgets import Cover  # noqa: E402
from handcrafted.window import HandcraftedWindow  # noqa: E402

folder = sandbox()
Adw.init()

T = 1_780_000_000


class FakeLauncher:
    '''Launcher's interface, without processes. Stamps last_played the way
    the real one does, since that is what puts a game in the hero.'''

    def __init__(self, library):
        self.library = library
        self.running_game = None
        self.clock = T
        self.refuse = {}  # game_id -> reason launch() fails with
        self._listeners = []

    def connect(self, callback):
        self._listeners.append(callback)

    def launch(self, game_id):
        if game_id in self.refuse:
            raise LaunchError(self.refuse[game_id])
        self.clock += 100
        self.library.start_session(game_id, now=self.clock)
        self.running_game = game_id
        self._notify()

    def stop(self):
        self.running_game = None
        self._notify()

    def _notify(self):
        for callback in self._listeners:
            callback()


def all_of(widget, test):
    found = [widget] if test(widget) else []
    child = widget.get_first_child()
    while child is not None:
        found.extend(all_of(child, test))
        child = child.get_next_sibling()
    return found


def texts(widget):
    return [w.get_label() for w in all_of(widget, lambda w: isinstance(
        w, Gtk.Label))]


def tiles(window):
    return all_of(window._hero_page, lambda w: w.has_css_class('hero-tile'))


def tile_ids(window):
    return [tile.game_id for tile in tiles(window)]


def tile(window, game_id):
    return next(t for t in tiles(window) if t.game_id == game_id)


def play_label(window):
    play = all_of(window._hero_page, lambda w: w.has_css_class('play'))[0]
    return play, ' '.join(texts(play))


def background(window):
    '''The layers behind the text: a cover and veils, or nothing.'''
    return [layer for layer in window._hero_page._layers
            if isinstance(layer, Cover) or any(
                layer.has_css_class(c)
                for c in ('hero-veil-across', 'hero-veil-up'))]


def picture(name):
    path = folder / 'incoming' / f'{name}.png'
    path.parent.mkdir(exist_ok=True)
    # A real image: thumbs.py has to be able to read it.
    from gi.repository import GdkPixbuf
    GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 32, 18).savev(
        str(path), 'png', [], [])
    return path


library = Library()
names = ['Kettle', 'Leaf', 'Ferry', 'Lamp', 'Moth', 'Never']
ids = {name: library.add(name, f'About {name}.', '/bin/true', now=T)
       for name in names}
images.replace(ids['Kettle'], [picture('kettle')])
launcher = FakeLauncher(library)

section('Nothing played yet')

window = HandcraftedWindow(library, launcher)
check('the window opens on the library', window.page == 'library')
check('with no way up to a hero', not window._rail._to_hero.get_visible())
window.show_hero()
check('and none to be had', window.page == 'library')
launcher.launch(ids['Leaf'])
launcher.stop()
check('once something was played, the way up is there',
      window._rail._to_hero.get_visible())
check('but the window stays where it is', window.page == 'library')
window.close_now()

section('With games played')

for name in ('Ferry', 'Lamp', 'Moth', 'Kettle'):
    launcher.launch(ids[name])
    launcher.stop()
window = HandcraftedWindow(library, launcher)
check('the window opens on the hero', window.page == 'hero')
check('the game played last is the hero', window._hero == ids['Kettle'])
check('four tiles, most recent first',
      tile_ids(window) == [ids[n] for n in ('Kettle', 'Moth', 'Lamp',
                                             'Ferry')], tile_ids(window))
check('the game played fifth-last is not among them',
      ids['Leaf'] not in tile_ids(window))
check('never played is never a tile', ids['Never'] not in tile_ids(window))
check('the hero tile is marked', tile(window, ids['Kettle']).has_css_class(
    'current'))
check('its title is shown', 'Kettle' in texts(window._hero_page))
check('with Played and Last',
      {'Played', 'Last'} <= set(texts(window._hero_page)))
check('a cover, under two veils', len(background(window)) == 3,
      background(window))

section('Tiles')

selected = window._selected
tile(window, ids['Lamp']).emit('clicked')
check('a click makes that game the hero', window._hero == ids['Lamp'])
check('and is marked', tile(window, ids['Lamp']).has_css_class('current')
      and not tile(window, ids['Kettle']).has_css_class('current'))
check('the page stays', window.page == 'hero')
check('the library selection stays', window._selected == selected)
check('no cover, no background at all', background(window) == [])
check('the tile keeps its placeholder',
      'L' in texts(tile(window, ids['Lamp'])))

section('Details and back')

details = next(b for b in all_of(window._hero_page, lambda w: isinstance(
    w, Gtk.Button)) if b.get_label() == 'Details')
details.emit('clicked')
check('Details goes to the library', window.page == 'library')
check('with that game selected', window._selected == ids['Lamp'])
window._rail._to_hero.emit('clicked')
check('"↑ Hero" goes back up', window.page == 'hero')

section('Running')

launcher.launch(ids['Lamp'])
check('the hero playing shows Stop',
      play_label(window)[1] == 'Running · Stop', play_label(window)[1])
check('the game playing is the first tile now, and still the hero',
      tile_ids(window)[0] == ids['Lamp'] and window._hero == ids['Lamp'])
check('the hero itself wears no badge',
      'RUNNING' not in texts(tile(window, ids['Lamp'])))
tile(window, ids['Kettle']).emit('clicked')
check('another hero cannot start while it runs',
      not play_label(window)[0].get_sensitive())
check('and the running one wears the badge',
      'RUNNING' in texts(tile(window, ids['Lamp'])))
launcher.stop()
check('afterwards Play is back', play_label(window)[1] == 'Play'
      and play_label(window)[0].get_sensitive())

section('When Play fails')

launcher.refuse = {ids['Kettle']: 'Permission denied'}
play_label(window)[0].emit('clicked')
check('the hero says why', 'Could not start: Permission denied'
      in texts(window._hero_page), texts(window._hero_page))
tile(window, ids['Moth']).emit('clicked')
tile(window, ids['Kettle']).emit('clicked')
check('choosing another hero and back does not forget it',
      'Could not start: Permission denied' in texts(window._hero_page))
details = next(b for b in all_of(window._hero_page, lambda w: isinstance(
    w, Gtk.Button)) if b.get_label() == 'Details')
details.emit('clicked')
check('Details still shows it, next to Fix path…',
      'Could not start: Permission denied' in texts(window._detail)
      and 'Fix path…' in texts(window._detail), texts(window._detail))
window.show_hero()
launcher.refuse = {}
play_label(window)[0].emit('clicked')
check('once it starts, the old reason is gone',
      not any(t.startswith('Could not start') for t in texts(window._hero_page))
      and play_label(window)[1] == 'Running · Stop')
launcher.stop()

section('Remembered')

window.emit('close-request')  # what close() does, without a mapped window
check('the hero is saved', state.load()['hero'] == ids['Kettle'])
window = HandcraftedWindow(library, launcher)
check('and comes back', window._hero == ids['Kettle'])
window.emit('close-request')  # what close() does, without a mapped window
saved = state.load()
saved['hero'] = 9999
state.save(saved)
window = HandcraftedWindow(library, launcher)
check('a hero that is gone falls back to the game played last',
      window._hero == ids['Kettle'], window._hero)

section('Deleting')

library.delete(ids['Kettle'])
window.refresh()
check('the next game moves up as the hero', window._hero == ids['Lamp'])
check('and the fifth-last played is a tile now',
      ids['Leaf'] in tile_ids(window))
for game in library.recent(limit=100):
    library.delete(game.id)
window.refresh()
check('once nothing played is left, there is no hero', window._hero is None)
check('and the window is in the library', window.page == 'library')
check('with no way up', not window._rail._to_hero.get_visible())

window.close_now()
library.close()
report(folder)
