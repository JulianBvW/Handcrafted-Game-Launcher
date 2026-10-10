'''The hero: the first page, one game at full window size.

Its cover fills the window under two veils, with title, description, Play
and Details at the bottom left, and under those the four games played most
recently as tiles. Without a cover there is nothing behind it but the
window's own background -- no stripes, no letter.
'''

from datetime import date

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, Pango  # noqa: E402

from . import formatting, images, launch, thumbs  # noqa: E402
from .i18n import _  # noqa: E402
from .widgets import (Cover, PlayButton, Ratio, glyph, label,  # noqa: E402
                      play_mode, problem_text)

GLYPH_HEIGHT = 40
INFO_WIDTH = 680
BODY_WIDTH = 540
BODY_LINES = 4
TILES = 4
TILE_WIDTH = 360


class _LayersLayout(Gtk.LayoutManager):
    '''Every child over the whole area, the later ones on top; sized by
    the last one alone.

    Not a Gtk.Overlay: that hands the children it lays over the base only
    the height they want at their narrowest, and the tiles, which are as
    high as their width calls for, came out flat.'''

    def do_get_request_mode(self, _widget):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, widget, orientation, for_size):
        content = widget.get_last_child()
        if content is None:
            return 0, 0, -1, -1
        minimum, natural, _, _ = content.measure(orientation, for_size)
        return minimum, natural, -1, -1

    def do_allocate(self, widget, width, height, _baseline):
        child = widget.get_first_child()
        while child is not None:
            child.allocate(width, height, -1, None)
            child = child.get_next_sibling()


class Hero(Gtk.Box):
    '''Calls on_play(game_id) for Play and Stop alike, on_details(game_id)
    for Details and on_choose(game_id) when a tile is clicked.'''

    def __init__(self, on_play, on_details, on_choose):
        super().__init__(hexpand=True, vexpand=True)
        self.set_layout_manager(_LayersLayout())
        self.add_css_class('hero')
        self._on_play = on_play
        self._on_details = on_details
        self._on_choose = on_choose
        self._layers = []
        self._drawn = None  # what it was last drawn from

    def show(self, game, tiles, running, error=None):
        '''Draw `game` (a library.Game) over `tiles`, the games played most
        recently. `running` is the id of the game that runs, or None;
        `error` why the last attempt to start `game` failed, if it did.

        Does nothing if all of that, its cover and the state of its
        executable are what it was last drawn from.'''
        cover = images.cover(game.id)
        problem = launch.check(game.executable)
        drawn = (game, tuple(tiles), running, error, problem, date.today(),
                 images.stamp([cover] + [images.cover(tile.id)
                                         for tile in tiles]))
        if drawn == self._drawn:
            return
        self._drawn = drawn

        for layer in self._layers:
            self.remove(layer)
        self._layers = []

        if cover is not None:
            self._add(Cover(cover, game.name, thumbs.LARGE))
            for veil in ('hero-veil-across', 'hero-veil-up'):
                box = Gtk.Box()
                box.add_css_class(veil)
                self._add(box)

        # Top left, in the corner the veils keep darkest.
        mark = glyph(height=GLYPH_HEIGHT)
        mark.set_halign(Gtk.Align.START)
        mark.set_valign(Gtk.Align.START)
        mark.add_css_class('hero-glyph')
        self._add(mark)

        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                         valign=Gtk.Align.END)
        column.append(self._info(game, running, error, problem))
        column.append(self._tiles(game, tiles, running))
        # Last, so it is on top -- and the one that decides the size: the
        # cover's own would only make the window as large as the image.
        self._add(column)

    def _add(self, layer):
        self.append(layer)
        self._layers.append(layer)

    # -- parts -------------------------------------------------------------

    def _info(self, game, running, error, problem):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.add_css_class('hero-info')

        title = label(game.name, 'hero-title', wrap=True)
        title.set_lines(2)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(title)

        if game.description:
            # At most four lines: a long description would push the title
            # out of the window. Details has all of it.
            body = label(game.description, 'hero-body', wrap=True)
            body.set_lines(BODY_LINES)
            body.set_ellipsize(Pango.EllipsizeMode.END)
            body.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            box.append(_clamped(body, BODY_WIDTH))

        if problem or error:
            box.append(label(problem_text(problem, error), 'danger'))

        row = Gtk.Box(spacing=12)
        row.add_css_class('hero-buttons')
        play = PlayButton('medium')
        play.set_mode(play_mode(game.id, problem, running))
        play.connect('clicked', lambda *_: self._on_play(game.id))
        row.append(play)

        details = Gtk.Button(label=_('Details'))
        details.add_css_class('outline-button')
        details.connect('clicked', lambda *_: self._on_details(game.id))
        row.append(details)

        stats = Gtk.Box(spacing=22, valign=Gtk.Align.CENTER)
        stats.add_css_class('hero-stats')
        for caption, value in (
                (_('Played'), formatting.playtime(game.playtime)),
                (_('Last'), formatting.last_played(game.last_played))):
            stat = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            stat.append(label(caption, 'hero-stat-label'))
            stat.append(label(value, 'hero-stat-value'))
            stats.append(stat)
        row.append(stats)
        box.append(row)
        return _clamped(box, INFO_WIDTH)

    def _tiles(self, game, tiles, running):
        grid = Gtk.Grid(column_homogeneous=True, column_spacing=20)
        grid.add_css_class('hero-tiles')
        for column in range(TILES):
            if column < len(tiles):
                cell = self._tile(tiles[column], tiles[column].id == game.id,
                                  tiles[column].id == running)
            else:
                # Fewer than four played: the others keep their width.
                cell = Gtk.Box(hexpand=True)
            grid.attach(cell, column, 0, 1, 1)
        return grid

    def _tile(self, game, current, running):
        picture = Gtk.Overlay()
        picture.set_child(Ratio(Cover(images.cover(game.id), game.name,
                                      TILE_WIDTH, stripe=8)))
        if running and not current:
            badge = label(_('Running').upper(), 'running-badge')
            badge.set_halign(Gtk.Align.START)
            badge.set_valign(Gtk.Align.START)
            picture.add_overlay(badge)

        name = label(game.name, 'tile-name')
        name.set_ellipsize(Pango.EllipsizeMode.END)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.append(picture)
        box.append(name)
        tile = Gtk.Button(hexpand=True)
        tile.set_child(box)
        tile.add_css_class('hero-tile')
        if current:
            tile.add_css_class('current')
        tile.game_id = game.id
        tile.connect('clicked', lambda *_: self._on_choose(game.id))
        return tile


def _clamped(child, width):
    '''`child` at most `width` wide, kept to the left.'''
    clamp = Adw.Clamp(maximum_size=width, tightening_threshold=width,
                      halign=Gtk.Align.START)
    clamp.set_child(child)
    return clamp
