'''Small pieces the rail, the detail column and the hero share.'''

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gsk', '4.0')
gi.require_version('Graphene', '1.0')
from gi.repository import Graphene, Gsk, Gtk, Pango  # noqa: E402

from . import config, thumbs  # noqa: E402
from .i18n import _  # noqa: E402


def status_label(status):
    '''The status as shown. The database keeps the English key.'''
    return {'new': _('New'), 'playing': _('Playing'), 'done': _('Done'),
            'abandoned': _('Abandoned')}[status]


def problem_text(problem, error):
    '''Why a game cannot start, as the detail column and the hero say it.
    `problem` is what launch.check() found, `error` why the last start
    failed; one of them is set.'''
    if problem == 'not executable':
        return _('Executable is not marked as runnable')
    if problem:
        return _('Executable not found')
    # It looked fine, and still would not start: say what the system said
    # rather than nothing at all.
    return _('Could not start: {reason}').format(reason=error)


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
    '''As wide as it is given, and as high as that width calls for.
    Gtk.AspectFrame only fits a child into the space it gets; it does not
    ask for the right height.'''

    def __init__(self, ratio, firm=False):
        super().__init__()
        self._ratio = ratio
        self._firm = firm

    def do_get_request_mode(self, _widget):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, _widget, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL:
            return 0, 0, -1, -1
        height = round(for_size / self._ratio) if for_size > 0 else 0
        if self._firm:
            # Also as minimum: inside a scrolled column, which gives its
            # content only the height it cannot do without, a mere wish is
            # squeezed flat.
            return height, height, -1, -1
        # The height as natural size, not as minimum: where the space is
        # fixed, as for the hero's tiles, a minimum would hold the window
        # open wider than it wants to be.
        return 0, height, -1, -1

    def do_allocate(self, widget, width, height, _baseline):
        # Given more height than the ratio calls for, keep the ratio and
        # sit at the top rather than stretch.
        _allocate_children(widget, width,
                           min(height, round(width / self._ratio)))


class _FixedLayout(Gtk.LayoutManager):
    '''Exactly this size, whatever the child would like. A Gtk.Picture
    asks for the size of its image -- twice the shown width, since the
    textures are loaded oversampled -- and size_request() is only ever a
    minimum, never a cap.'''

    def __init__(self, width, height):
        super().__init__()
        self._size = (width, height)

    def do_measure(self, _widget, orientation, _for_size):
        size = self._size[0 if orientation == Gtk.Orientation.HORIZONTAL
                          else 1]
        return size, size, -1, -1

    def do_allocate(self, widget, width, height, _baseline):
        _allocate_children(widget, width, height)


def _allocate_children(widget, width, height):
    child = widget.get_first_child()
    while child is not None:
        child.allocate(width, height, -1, None)
        child = child.get_next_sibling()


def _holder(layout, child, expand):
    # A plain Box with its layout swapped, rather than a Gtk.Widget
    # subclass: PyGObject never calls do_dispose on those, so a subclass
    # could not let go of its child and GTK would complain on every rebuild.
    box = Gtk.Box(hexpand=expand, vexpand=False, valign=Gtk.Align.START)
    box.set_layout_manager(layout)
    box.append(child)
    return box


def Ratio(child, ratio=16 / 9, firm=False):  # noqa: N802 -- reads like a widget
    '''`child` at a fixed aspect ratio, as wide as it is given. `firm`
    insists on that height even where the space is short, so a scrolled
    column scrolls rather than squeezes it.'''
    return _holder(_RatioLayout(ratio, firm), child, expand=True)


def Fixed(child, width, height):  # noqa: N802
    '''`child` at exactly width x height.'''
    box = _holder(_FixedLayout(width, height), child, expand=False)
    box.set_halign(Gtk.Align.START)
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


def play_mode(game_id, problem, running):
    '''What a game's Play button shows: `problem` from launch.check(),
    `running` the id of the game that runs or None.'''
    if problem:
        return 'broken'
    if running is None:
        return 'play'
    return 'running' if running == game_id else 'blocked'


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
        tooltip = _('Another game is running') if mode == 'blocked' else None
        if tooltip != self.get_tooltip_text():
            # Only when it changes: setting one costs more than the rest of
            # this together.
            self.set_tooltip_text(tooltip)


# -- the glyph ---------------------------------------------------------------

# Where the drawing lies inside glyph.svg's 288-unit square: x, y, width,
# height. Lined up by what is drawn, not by the square around it, the glyph
# can be made exactly as tall as a word.
GLYPH_BOX = 288
GLYPH_INK = (12, 8, 264, 272)


class _GlyphLayout(Gtk.LayoutManager):
    '''The glyph with its drawing `height` px tall -- or, given a `word`
    label, as tall as that word is inked, from the top of its tallest
    letter to the bottom of its lowest, and on the same baseline.'''

    def __init__(self, height=None, word=None):
        super().__init__()
        self._height = height
        self._word = word

    def _metrics(self):
        '''(scale from glyph units to pixels, drawing height, how much of
        it lies above the baseline)'''
        if self._word is None:
            return self._height / GLYPH_INK[3], self._height, -1
        layout = self._word.get_layout()
        ink, _logical = layout.get_pixel_extents()
        baseline = layout.get_baseline() / Pango.SCALE
        return ink.height / GLYPH_INK[3], ink.height, baseline - ink.y

    def do_measure(self, _widget, orientation, _for_size):
        scale, height, above = self._metrics()
        if orientation == Gtk.Orientation.HORIZONTAL:
            width = round(GLYPH_INK[2] * scale)
            return width, width, -1, -1
        above = round(above) if above >= 0 else -1
        return round(height), round(height), above, above

    def do_allocate(self, widget, _width, height, baseline):
        scale, drawing, above = self._metrics()
        box = round(GLYPH_BOX * scale)
        # Where the drawing starts: on a shared baseline, as far above it as
        # the word reaches; otherwise centred in the height given.
        if baseline >= 0 and above >= 0:
            top = baseline - above
        else:
            top = (height - drawing) / 2
        # The square is larger than the drawing: shifted so the drawing
        # starts there.
        point = Graphene.Point()
        point.init(-GLYPH_INK[0] * scale, top - GLYPH_INK[1] * scale)
        widget.get_first_child().allocate(
            box, box, -1, Gsk.Transform.new().translate(point))


def glyph(height=None, word=None):
    '''Handcrafted's glyph, the needle and thread, at a fixed `height` or
    as tall as the label `word` (see _GlyphLayout).'''
    picture = Gtk.Picture.new_for_paintable(
        thumbs.texture(config.GLYPH_FILE, 128))
    picture.set_can_shrink(True)
    picture.set_content_fit(Gtk.ContentFit.CONTAIN)
    box = Gtk.Box(hexpand=False, vexpand=False)
    box.set_layout_manager(_GlyphLayout(height, word))
    box.append(picture)
    box.add_css_class('glyph')
    return box
