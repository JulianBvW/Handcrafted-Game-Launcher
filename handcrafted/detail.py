'''The detail column: everything about the selected game.

Scrolls by itself. The cover sits faded behind the top of the column, and
over it, held to 1100 px: the title row with Play, the description, four
figures, and every image.
'''

from datetime import date

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import formatting, images, launch, thumbs  # noqa: E402
from .i18n import _  # noqa: E402
from .library import STATUSES  # noqa: E402
from .widgets import (Cover, PlayButton, Ratio, dot, label,  # noqa: E402
                      play_mode, problem_text, status_label)

CONTENT_WIDTH = 1100
BACKDROP_HEIGHT = 440
GALLERY_WIDTH = CONTENT_WIDTH // 2


class Detail(Gtk.ScrolledWindow):
    '''Calls on_play(game_id) for Play and Stop alike, on_edit(game_id) for
    the gear and on_fix_path(game_id) for "Fix path…". The status menu acts
    through the window's `win.status` action.'''

    def __init__(self, on_play, on_edit, on_fix_path):
        super().__init__(hexpand=True, vexpand=True)
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.add_css_class('detail')
        self._on_fix_path = on_fix_path
        self._shown = None
        self._drawn = None  # what it was last drawn from

        # Built once and moved into each new drawing: a MenuButton builds
        # its whole popover when it gets a menu, and setting a tooltip is
        # not free either -- too much to repeat for every game clicked.
        self._play = PlayButton('large')
        self._play.set_valign(Gtk.Align.END)
        self._play.connect('clicked', lambda *_: on_play(self._shown))
        self._gear = Gtk.Button(valign=Gtk.Align.END)
        self._gear.set_child(Gtk.Image(icon_name='emblem-system-symbolic',
                                       pixel_size=22))
        self._gear.add_css_class('ring-button')
        self._gear.set_tooltip_text(_('Edit game'))
        self._gear.connect('clicked', lambda *_: on_edit(self._shown))
        self._status_menu = self._build_status_menu()

    def show(self, game, running, error=None):
        '''Draw `game` (a library.Game, or None for an empty library).
        `running` is the id of the game that runs, or None. `error` is why
        the last attempt to start this game failed, if it did.

        Does nothing if all of that, the images and the state of the
        executable are what it was last drawn from.'''
        pictures = images.listing(game.id) if game is not None else []
        problem = launch.check(game.executable) if game is not None else None
        drawn = (game, running, error, problem, date.today(),
                 images.stamp(pictures))
        if drawn == self._drawn:
            return
        self._drawn = drawn

        if game is None:
            empty = label(_('Your library is empty'), 'meta-muted',
                          xalign=0.5)
            empty.set_valign(Gtk.Align.CENTER)
            self.set_child(empty)
            self._shown = None
            return

        overlay = Gtk.Overlay()
        overlay.set_child(self._backdrop(game, pictures))
        content = self._content(game, pictures, running, error, problem)
        overlay.add_overlay(content)
        # The content, not the backdrop, decides how tall the column is.
        overlay.set_measure_overlay(content, True)

        changed = game.id != self._shown
        position = self.get_vadjustment().get_value()
        self.set_child(overlay)
        self._shown = game.id
        # Another game starts at its top, not wherever the last one was. The
        # same game, drawn again after a status change or a game ending,
        # stays where it was scrolled to -- once the new content has a size.
        target = 0 if changed else position
        GLib.idle_add(self._scroll_to, target)

    def _scroll_to(self, value):
        self.get_vadjustment().set_value(value)
        return GLib.SOURCE_REMOVE

    # -- parts -------------------------------------------------------------

    def _backdrop(self, game, pictures):
        backdrop = Gtk.Overlay(valign=Gtk.Align.START)
        backdrop.set_size_request(-1, BACKDROP_HEIGHT)
        if pictures:
            # The hero's size: the same texture serves both.
            backdrop.set_child(Cover(pictures[0], game.name, thumbs.LARGE))
            backdrop.add_css_class('backdrop')
            veil = Gtk.Box()
            veil.add_css_class('backdrop-veil')
            backdrop.add_overlay(veil)
        return backdrop

    def _content(self, game, pictures, running, error, problem):
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        column.add_css_class('detail-content')
        column.append(self._title_row(game, running, problem))

        if problem or error:
            column.append(self._error_row(game, problem, error))

        if game.description:
            body = label(game.description, 'detail-body', wrap=True)
            body.set_max_width_chars(80)
            body.set_halign(Gtk.Align.START)
            column.append(body)

        column.append(self._figures(game))
        if pictures:
            # Without images, nothing: a placeholder here would only say
            # what the empty space already does.
            column.append(self._gallery(game, pictures))

        clamp = Adw.Clamp(maximum_size=CONTENT_WIDTH,
                          tightening_threshold=CONTENT_WIDTH)
        clamp.set_child(column)
        clamp.set_valign(Gtk.Align.START)
        return clamp

    def _title_row(self, game, running, problem):
        eyebrow = Gtk.Box(spacing=8)
        eyebrow.add_css_class('eyebrow')
        eyebrow.append(dot(game.status, size=8))
        eyebrow.append(label(status_label(game.status).upper(), 'eyebrow'))
        if game.version:
            eyebrow.append(label('·', 'eyebrow', 'dim'))
            eyebrow.append(label(game.version.upper(), 'eyebrow'))

        title = label(game.name, 'detail-title', wrap=True)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       hexpand=True, valign=Gtk.Align.END)
        left.append(eyebrow)
        left.append(title)

        self._play.set_mode(play_mode(game.id, problem, running))

        row = Gtk.Box(spacing=24)
        row.append(left)
        row.append(_adopt(self._play))
        row.append(_adopt(self._gear))
        return row

    def _error_row(self, game, problem, error):
        row = Gtk.Box(spacing=12)
        row.append(label(problem_text(problem, error), 'danger'))
        fix = Gtk.Button(label=_('Fix path…'))
        fix.add_css_class('quiet-button')
        fix.connect('clicked', lambda *_: self._on_fix_path(game.id))
        row.append(fix)
        return row

    def _figures(self, game):
        grid = Gtk.Grid(column_homogeneous=True, column_spacing=24)
        grid.add_css_class('figures')
        for column, (caption, value) in enumerate((
                (_('Playtime'), formatting.playtime(game.playtime)),
                (_('Last played'), formatting.last_played(game.last_played)),
                (_('Added'), formatting.added(game.added)))):
            grid.attach(self._figure(caption, label(value, 'figure')),
                        column, 0, 1, 1)
        self._status_dot.set_css_classes(['dot', f'status-{game.status}'])
        self._status_text.set_label(status_label(game.status))
        # Its menu may still be on its way out when a status chosen in it
        # redraws the column; closed first, it moves cleanly.
        self._status_menu.popdown()
        grid.attach(self._figure(_('Status'), _adopt(self._status_menu)),
                    3, 0, 1, 1)
        return grid

    def _figure(self, caption, value):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(label(caption.upper(), 'mono-label'))
        box.append(value)
        return box

    def _build_status_menu(self):
        '''Looks like the other figures; is a menu. Its face is filled in
        by _figures().'''
        menu = Gio.Menu()
        for status in STATUSES:
            menu.append(status_label(status), f'win.status::{status}')

        face = Gtk.Box(spacing=10)
        self._status_dot = dot('new', size=10)
        self._status_text = label('', 'figure')
        face.append(self._status_dot)
        face.append(self._status_text)
        arrow = Gtk.Image(icon_name='pan-down-symbolic', pixel_size=14)
        arrow.add_css_class('dim')
        face.append(arrow)

        button = Gtk.MenuButton(menu_model=menu, halign=Gtk.Align.START)
        button.set_child(face)
        button.add_css_class('status-menu')
        return button

    def _gallery(self, game, pictures):
        '''Every image whole, in its own shape: two columns, each image
        going to the one that is shorter so far, so the columns stay about
        even and the order still reads from the top.'''
        columns = [Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                           valign=Gtk.Align.START) for _ in range(2)]
        heights = [0.0, 0.0]  # in widths of a column
        for path in pictures:
            texture = thumbs.texture(path, GALLERY_WIDTH)
            ratio = (texture.get_width() / texture.get_height()
                     if texture is not None else 16 / 9)
            cell = Ratio(Cover(path, game.name, GALLERY_WIDTH), ratio,
                         firm=True)
            cell.add_css_class('gallery-image')
            shorter = heights.index(min(heights))
            columns[shorter].append(cell)
            heights[shorter] += 1 / ratio

        gallery = Gtk.Box(spacing=16, homogeneous=True)
        gallery.add_css_class('gallery')
        for column in columns:
            gallery.append(column)
        return gallery

def _adopt(widget):
    '''`widget`, taken out of the drawing it was last in, so it can go into
    the new one.'''
    parent = widget.get_parent()
    if parent is not None:
        parent.remove(widget)
    return widget
