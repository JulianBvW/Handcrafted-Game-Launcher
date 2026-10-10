'''Small pieces the rail, the detail column and later the hero share.'''

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa: E402

from . import thumbs  # noqa: E402
from .i18n import _  # noqa: E402


def status_label(status):
    '''The status as shown. The database keeps the English key.'''
    return {'new': _('New'), 'playing': _('Playing'), 'done': _('Done'),
            'abandoned': _('Abandoned')}[status]


def initial(name):
    '''The letter a placeholder shows: the first one, skipping a leading
    "The ", so "The Leaf" is filed under L the way a shelf would.'''
    name = name.strip()
    if name.lower().startswith('the ') and name[4:].strip():
        name = name[4:].strip()
    return name[:1].upper() or '?'


def label(text='', *classes, xalign=0.0, wrap=False):
    widget = Gtk.Label(label=text, xalign=xalign)
    for css_class in classes:
        widget.add_css_class(css_class)
    if wrap:
        widget.set_wrap(True)
        widget.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
    return widget


class _RatioLayout(Gtk.LayoutManager):
    '''As wide as it is given, and exactly as high as that width calls for.
    Gtk.AspectFrame only fits a child into the space it gets; it does not
    ask for the right height.'''

    def __init__(self, ratio):
        super().__init__()
        self._ratio = ratio

    def do_get_request_mode(self, _widget):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, _widget, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL:
            return 0, 0, -1, -1
        height = round(for_size / self._ratio) if for_size > 0 else 0
        return height, height, -1, -1

    def do_allocate(self, widget, width, height, baseline):
        child = widget.get_first_child()
        while child is not None:
            child.allocate(width, height, baseline, None)
            child = child.get_next_sibling()


def Ratio(child, ratio=16 / 9):  # noqa: N802 -- reads like the widget it is
    '''`child` held at a fixed aspect ratio.

    A plain Box with its layout swapped, rather than a Gtk.Widget subclass:
    PyGObject never calls do_dispose on those, so a subclass could not let
    go of its child and GTK would complain on every rebuild.
    '''
    box = Gtk.Box(hexpand=True)
    box.set_layout_manager(_RatioLayout(ratio))
    box.append(child)
    return box


class Cover(Gtk.Box):
    '''An image cropped to fill its box, or the striped placeholder with an
    initial when there is none.

    `path` is the image file or None. `width` is the width it is shown at,
    for loading it at the right size. `stripe` names the placeholder's grid
    (6, 8 or 12 px) and `initial_class` the size of its letter.
    '''

    def __init__(self, path, name, width, stripe=8, initial_class=None,
                 placeholder_text=None):
        super().__init__(hexpand=True, vexpand=True)
        self.add_css_class('cover')
        self.set_overflow(Gtk.Overflow.HIDDEN)

        texture = thumbs.texture(path, width) if path else None
        if texture is not None:
            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_content_fit(Gtk.ContentFit.COVER)
            picture.set_can_shrink(True)
            picture.set_hexpand(True)
            picture.set_vexpand(True)
            self.append(picture)
            return

        self.add_css_class('placeholder')
        self.add_css_class(f'stripes-{stripe}')
        if placeholder_text is not None:
            text = label(placeholder_text, 'mono', 'ghost', xalign=0.5)
        else:
            text = label(initial(name), 'initial', xalign=0.5)
            if initial_class:
                text.add_css_class(initial_class)
        text.set_hexpand(True)
        text.set_halign(Gtk.Align.CENTER)
        text.set_valign(Gtk.Align.CENTER)
        self.append(text)


def dot(status=None, size=8, accent=False):
    '''A small round mark: a status colour, or the accent for "running".'''
    widget = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    widget.set_size_request(size, size)
    widget.add_css_class('dot')
    widget.add_css_class('accent' if accent else f'status-{status}')
    return widget


class PlayButton(Gtk.Button):
    '''Play, or "Running · Stop" while this game runs, or Play greyed out
    while another one does. `size` is 'large' (detail) or 'medium' (hero).
    '''

    def __init__(self, size='large'):
        super().__init__()
        self.add_css_class('play')
        self.add_css_class(size)
        box = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        self._shape = Gtk.Box(valign=Gtk.Align.CENTER)
        self._text = Gtk.Label()
        box.append(self._shape)
        box.append(self._text)
        self.set_child(box)
        self.set_mode('play')

    def set_mode(self, mode):
        '''`play`, `running`, `blocked` (another game runs) or `broken`
        (the launcher is missing).'''
        running = mode == 'running'
        self.set_css_classes(
            [c for c in self.get_css_classes()
             if c not in ('running', 'triangle', 'square')]
            + (['running'] if running else []))
        self._shape.set_css_classes(['square' if running else 'triangle'])
        self._text.set_label(_('Running · Stop') if running else _('Play'))
        self.set_sensitive(mode in ('play', 'running'))
        self.set_tooltip_text(_('Another game is running')
                              if mode == 'blocked' else None)
