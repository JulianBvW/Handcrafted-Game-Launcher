'''The rail: the whole library as a list, grouped by status.

340 px on the left. A fixed head -- title, totals, the + button and the
Everything / Now playing switch -- over a list that scrolls by itself.
'''

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Pango  # noqa: E402

from . import formatting, images  # noqa: E402
from .i18n import _  # noqa: E402
from .widgets import Cover, Fixed, dot, label, status_label  # noqa: E402

WIDTH = 340
THUMB_WIDTH = 104
THUMB_HEIGHT = 59  # 104 at 16:9


class Rail(Gtk.Box):
    '''Calls on_select(game_id) when a game is clicked and on_hero() for
    the way back up. The window decides what is selected and tells the rail
    through refresh().'''

    def __init__(self, library, on_select, on_add, on_hero):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class('rail')
        self.set_size_request(WIDTH, -1)
        self.set_hexpand(False)

        self._library = library
        self._on_select = on_select
        self._only_playing = False
        self._selected = None
        self._running = None
        self._has_hero = False

        head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        head.add_css_class('rail-head')
        self.append(head)

        # Back to the hero; there only while there is one (DESIGN §13,
        # fallback).
        self._to_hero = Gtk.Button(label=_('↑ Hero'), halign=Gtk.Align.START,
                                   visible=False)
        self._to_hero.add_css_class('back-button')
        self._to_hero.connect('clicked', lambda *_: on_hero())
        head.append(self._to_hero)

        title_row = Gtk.Box(spacing=10)
        # Both on the baseline, so the small totals sit on the same line as
        # the big title rather than floating at its middle.
        title = label(_('Library'), 'section-title')
        title.set_valign(Gtk.Align.BASELINE_FILL)
        title_row.append(title)
        self._totals = label('', 'mono', 'meta-muted')
        self._totals.set_valign(Gtk.Align.BASELINE_FILL)
        title_row.append(self._totals)
        title_row.append(Gtk.Box(hexpand=True))
        add = Gtk.Button(label='+', valign=Gtk.Align.CENTER)
        add.add_css_class('icon-button')
        add.set_tooltip_text(_('Add a game'))
        add.connect('clicked', lambda *_: on_add())
        title_row.append(add)
        head.append(title_row)

        switch = Gtk.Box(homogeneous=True)
        switch.add_css_class('switch')
        self._everything = Gtk.ToggleButton(label=_('Everything'),
                                            active=True)
        self._playing = Gtk.ToggleButton()
        self._playing.set_group(self._everything)
        playing_box = Gtk.Box(spacing=7, halign=Gtk.Align.CENTER)
        playing_box.append(dot(size=7, accent=True))
        self._playing_label = Gtk.Label()
        playing_box.append(self._playing_label)
        self._playing.set_child(playing_box)
        for button in (self._everything, self._playing):
            switch.append(button)
        self._playing.connect('toggled', self._on_switch)
        head.append(switch)

        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._list.add_css_class('rail-list')
        self._list.connect('row-activated', self._on_row_activated)
        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self._list)
        self.append(scroller)

    # -- drawing -----------------------------------------------------------

    def refresh(self, selected, running, has_hero=False):
        self._selected = selected
        self._has_hero = has_hero
        self._to_hero.set_visible(has_hero)
        self._running = running

        count, seconds = self._library.totals()
        self._totals.set_label(f'{count} · {formatting.playtime(seconds)}')

        groups = self._library.grouped()
        playing = next((len(games) for status, games in groups
                        if status == 'playing'), 0)
        if self._only_playing:
            self._playing_label.set_label(
                _('Now playing · {n}').format(n=playing))
            groups = [(s, g) for s, g in groups if s == 'playing']
        else:
            self._playing_label.set_label(_('Now playing'))

        self._list.remove_all()
        for status, games in groups:
            self._list.append(self._group_head(status, len(games)))
            for game in games:
                self._list.append(self._game_row(game))

    def _group_head(self, status, count):
        box = Gtk.Box(spacing=8)
        box.add_css_class('group-head')
        box.append(dot(status, size=7))
        box.append(label(status_label(status).upper(), 'mono-label'))
        box.append(label(str(count), 'mono-label', 'count'))
        row = Gtk.ListBoxRow(child=box, activatable=False, selectable=False)
        row.add_css_class('plain')
        return row

    def _game_row(self, game):
        thumb = Gtk.Overlay(hexpand=False, valign=Gtk.Align.CENTER)
        thumb.add_css_class('rail-thumb')
        thumb.set_child(Fixed(
            Cover(images.cover(game.id), game.name, THUMB_WIDTH, stripe=6,
                  initial_class='initial-22'),
            THUMB_WIDTH, THUMB_HEIGHT))
        if game.id == self._running:
            mark = dot(size=8, accent=True)
            mark.set_halign(Gtk.Align.START)
            mark.set_valign(Gtk.Align.START)
            mark.set_margin_start(5)
            mark.set_margin_top(5)
            thumb.add_overlay(mark)

        name = label(game.name, 'row-name')
        name.set_ellipsize(Pango.EllipsizeMode.END)
        meta = label(f'{formatting.playtime(game.playtime)} · '
                     f'{formatting.last_played(game.last_played)}',
                     'mono', 'row-meta')
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                       valign=Gtk.Align.CENTER, hexpand=True)
        text.append(name)
        text.append(meta)

        box = Gtk.Box(spacing=12)
        box.append(thumb)
        box.append(text)
        row = Gtk.ListBoxRow(child=box)
        row.add_css_class('rail-row')
        if game.id == self._selected:
            row.add_css_class('selected')
        row.game_id = game.id
        return row

    # -- input -------------------------------------------------------------

    def _on_row_activated(self, _list, row):
        game_id = getattr(row, 'game_id', None)
        if game_id is not None:
            self._on_select(game_id)

    def _on_switch(self, button):
        self._only_playing = button.get_active()
        self.refresh(self._selected, self._running, self._has_hero)
