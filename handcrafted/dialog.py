'''The dialog for adding and editing a game.

Laid over the window rather than opened as one: a dark sheet across all of
it, the form standing directly on it, no card and no frame. One piece for
both jobs -- "New game" without a game, "Edit game" with one.

It writes nothing itself. What was entered goes to on_save, and the window
does the writing, so everything that changes the library happens in one
place. Until then the images are only a list of paths here: reordering and
removing touch nothing on disk, and Cancel leaves everything as it was.
Images loaded from links wait in a download folder of this dialog's own
until then.
'''

import os
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import download  # noqa: E402
from .i18n import _  # noqa: E402
from .widgets import Cover, Fixed, Ratio, label  # noqa: E402

WIDTH = 1000
RIGHT_COLUMN = 451  # 1 : 0.9 of what is left beside the 48 px gap
THUMB_WIDTH = 84
THUMB_HEIGHT = 47   # 84 at 16:9
DESCRIPTION_LINES = 3
LINE_HEIGHT = 24    # 16 px at 1.5
LINK_LINES = 4
LINK_LINE_HEIGHT = 18  # 12 px mono
SHOWN_URL = 48      # longer links are shortened in the middle


class GameDialog(Gtk.Box):
    '''`game` is a library.Game to edit, or None to add one. `pictures` are
    its current images in order. `running` greys out Delete.

    on_save(fields, pictures, pictures_changed), on_cancel(),
    on_delete(). `focus` is 'name' or 'executable' -- the latter for
    "Fix path…".
    '''

    def __init__(self, game, pictures, running, on_save, on_cancel,
                 on_delete, focus='name', folder=None):
        super().__init__(hexpand=True, vexpand=True)
        self.add_css_class('scrim')
        self._game = game
        self._pictures = list(pictures)
        self._pictures_changed = False
        self._on_save = on_save
        self._on_cancel = on_cancel
        self._on_delete = on_delete
        self._armed = False
        self._folder = folder  # where loaded images wait until Save
        self._loader = download.Loader(GLib.idle_add)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect('key-pressed', self._on_key)
        self.add_controller(keys)

        columns = Gtk.Box(spacing=48)
        columns.append(self._form())
        columns.append(self._images_column())

        clamp = Adw.Clamp(maximum_size=WIDTH, tightening_threshold=WIDTH,
                          valign=Gtk.Align.CENTER)
        clamp.set_child(columns)
        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(clamp)
        self.append(scroller)

        self._update_primary()
        self.set_running(running)
        self.first_focus = (self._executable if focus == 'executable'
                            else self._name)
        GLib.idle_add(self._focus, self.first_focus)

    # -- building ----------------------------------------------------------

    def _form(self):
        game = self._game
        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22,
                       hexpand=True)

        form.append(label(_('Edit game') if game else _('New game'),
                          'dialog-title'))

        self._name = Gtk.Entry(text=game.name if game else '',
                               placeholder_text=_('Name'))
        self._name.add_css_class('underlined')
        self._name.add_css_class('name-field')
        self._name.connect('changed', lambda *_: self._update_primary())
        self._name.connect('activate', lambda *_: self._save())
        form.append(self._name)

        self._description = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                         accepts_tab=False)
        self._description.get_buffer().set_text(
            game.description if game else '')
        self._description.add_css_class('description-field')
        # Three lines, always: longer text scrolls inside the field rather
        # than pushing the buttons down.
        frame = Gtk.ScrolledWindow(propagate_natural_height=False)
        frame.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        frame.set_size_request(-1, DESCRIPTION_LINES * LINE_HEIGHT)
        frame.set_child(self._description)
        frame.add_css_class('underlined')
        form.append(frame)

        self._version = Gtk.Entry(text=game.version if game else '',
                                  placeholder_text=_('Version (optional)'))
        self._version.add_css_class('boxed')
        form.append(self._version)

        path_row = Gtk.Box(spacing=10)
        self._executable = Gtk.Entry(
            text=game.executable if game else '', hexpand=True,
            placeholder_text=_('Executable (.sh)'))
        self._executable.add_css_class('boxed')
        path_row.append(self._executable)
        browse = Gtk.Button(label=_('Browse'))
        browse.add_css_class('browse')
        browse.connect('clicked', self._on_browse)
        path_row.append(browse)
        form.append(path_row)

        buttons = Gtk.Box(spacing=12)
        buttons.add_css_class('dialog-buttons')
        self._primary = Gtk.Button(
            label=_('Save changes') if game else _('Add to library'))
        self._primary.add_css_class('primary')
        self._primary.connect('clicked', lambda *_: self._save())
        buttons.append(self._primary)
        cancel = Gtk.Button(label=_('Cancel'))
        cancel.add_css_class('quiet-button')
        cancel.connect('clicked', lambda *_: self._on_cancel())
        buttons.append(cancel)
        if game is not None:
            buttons.append(Gtk.Box(hexpand=True))
            self._delete = Gtk.Button(label=_('Delete game'))
            self._delete.add_css_class('delete')
            self._delete.connect('clicked', self._on_delete_clicked)
            buttons.append(self._delete)
        else:
            self._delete = None
        form.append(buttons)

        self._error = label('', 'danger', wrap=True)
        self._error.set_visible(False)
        form.append(self._error)
        return form

    def _images_column(self):
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14,
                         hexpand=False)
        column.set_size_request(RIGHT_COLUMN, -1)
        self._preview_slot = Gtk.Box()
        column.append(self._preview_slot)
        self._thumbs = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE, column_spacing=8,
            row_spacing=8, max_children_per_line=12,
            homogeneous=False, valign=Gtk.Align.START)
        self._thumbs.add_css_class('dialog-thumbs')
        column.append(self._thumbs)
        self._draw_images()
        if self._folder is not None:
            column.append(self._link_field())
        return column

    def _link_field(self):
        '''Paste links, press Load: the images land in the list above.'''
        self._links = Gtk.TextView(wrap_mode=Gtk.WrapMode.CHAR,
                                   accepts_tab=False)
        self._links.add_css_class('links-field')
        buffer = self._links.get_buffer()
        buffer.connect('changed', lambda *_: self._update_load())

        frame = Gtk.ScrolledWindow(propagate_natural_height=False)
        frame.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        frame.set_size_request(-1, LINK_LINES * LINK_LINE_HEIGHT)
        frame.set_child(self._links)
        # Gtk.TextView has no placeholder of its own.
        self._links_hint = label(_('One image URL per line'),
                                 'links-placeholder')
        self._links_hint.set_valign(Gtk.Align.START)
        self._links_hint.set_can_target(False)
        field = Gtk.Overlay()
        field.add_css_class('links-box')
        field.set_child(frame)
        field.add_overlay(self._links_hint)

        self._load = Gtk.Button(label=_('Load'), halign=Gtk.Align.END)
        self._load.add_css_class('load')
        self._load.connect('clicked', lambda *_: self._start_loading())

        self._load_summary = label('', 'danger')
        self._load_reasons = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                     spacing=2)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.append(field)
        box.append(self._load)
        box.append(self._load_summary)
        box.append(self._load_reasons)
        self._show_failures([], 0)
        self._update_load()
        return box

    def _draw_images(self):
        '''The preview and the row of thumbnails, from self._pictures.'''
        child = self._preview_slot.get_first_child()
        if child is not None:
            self._preview_slot.remove(child)
        first = self._pictures[0] if self._pictures else None
        preview = Ratio(Cover(first, '', RIGHT_COLUMN, stripe=12,
                              placeholder_text=_('cover image')))
        preview.add_css_class('cover-preview')
        self._preview_slot.append(preview)

        self._thumbs.remove_all()
        for n, path in enumerate(self._pictures):
            self._thumbs.append(self._thumb(n, path))

    def _thumb(self, n, path):
        picture = Gtk.Button()
        picture.set_child(Fixed(Cover(path, '', THUMB_WIDTH, stripe=6),
                                THUMB_WIDTH, THUMB_HEIGHT))
        picture.add_css_class('dialog-thumb')
        picture.set_tooltip_text(None if n == 0 else _('Make cover'))
        picture.connect('clicked', lambda *_: self._make_cover(n))

        thumb = Gtk.Overlay(halign=Gtk.Align.START, valign=Gtk.Align.START)
        thumb.set_child(picture)
        if n == 0:
            badge = label(_('COVER'), 'cover-badge', xalign=0.5)
            badge.set_halign(Gtk.Align.START)
            badge.set_valign(Gtk.Align.END)
            badge.set_margin_start(4)
            badge.set_margin_bottom(4)
            badge.set_can_target(False)
            thumb.add_overlay(badge)
        remove = Gtk.Button(label='×', halign=Gtk.Align.END,
                            valign=Gtk.Align.START)
        remove.add_css_class('remove-badge')
        remove.set_margin_end(3)
        remove.set_margin_top(3)
        remove.set_tooltip_text(_('Remove'))
        remove.connect('clicked', lambda *_: self._remove(n))
        thumb.add_overlay(remove)
        return thumb

    # -- images ------------------------------------------------------------

    def _make_cover(self, n):
        if n == 0:
            return
        self._pictures.insert(0, self._pictures.pop(n))
        self._pictures_changed = True
        self._draw_images()

    def _remove(self, n):
        del self._pictures[n]
        self._pictures_changed = True
        self._draw_images()

    # -- loading -----------------------------------------------------------

    def _link_text(self):
        buffer = self._links.get_buffer()
        return buffer.get_text(buffer.get_start_iter(),
                               buffer.get_end_iter(), False)

    def _update_load(self):
        text = self._link_text()
        self._links_hint.set_visible(not text)
        self._load.set_sensitive(bool(text.strip())
                                 and not self._loader.running)

    def _start_loading(self):
        links, rejected, later = download.parse(self._link_text())
        self._rejected, self._later = rejected, later
        self._total = len(links) + len(rejected)
        if not links:
            self._finished([])
            return
        self._loader.start(links, self._folder, self._progress,
                           self._arrived, self._finished)
        self._update_load()

    def _progress(self, n, total):
        self._load.set_label(_('Loading {n}/{total}…').format(
            n=n, total=total))
        self._load.set_sensitive(False)

    def _arrived(self, url, path):
        '''One image is in: appended at the end, and its line leaves the
        field. Only that line -- anything typed meanwhile stays.'''
        self._pictures.append(path)
        self._pictures_changed = True
        self._draw_images()
        lines = self._link_text().splitlines()
        for n, line in enumerate(lines):
            if line.strip() == url:
                del lines[n]
                break
        self._links.get_buffer().set_text(
            '\n'.join(line for line in lines if line.strip()))

    def _finished(self, failed):
        '''What failed stayed in the field; say why.'''
        self._show_failures(failed + self._rejected, self._total)
        self._load.set_label(_('Load'))
        self._update_load()

    def _show_failures(self, failures, total):
        self._load_summary.set_visible(bool(failures))
        self._load_summary.set_label(
            _('{failed} of {total} failed').format(failed=len(failures),
                                                   total=total))
        while (child := self._load_reasons.get_first_child()) is not None:
            self._load_reasons.remove(child)
        for line, reason in failures:
            self._load_reasons.append(label(
                f'{_shorten(line)} — {reason}', 'mono', 'load-reason',
                wrap=True))

    def stop_loading(self):
        '''Whatever is still on its way is not wanted any more.'''
        if self._loader.running:
            self._loader.cancel()
            if self._folder is not None:
                self._load.set_label(_('Load'))
                self._update_load()

    # -- state -------------------------------------------------------------

    def set_running(self, running):
        '''A game that runs is not deleted from under itself.'''
        if self._delete is None:
            return
        if running:
            self._disarm()  # a confirmation from before does not carry over
        self._delete.set_sensitive(not running)
        self._delete.set_tooltip_text(_('Stop the game first')
                                      if running else None)

    def show_error(self, message):
        self._error.set_label(message)
        self._error.set_visible(True)

    def _disarm(self):
        self._armed = False
        self._delete.set_label(_('Delete game'))
        self._delete.remove_css_class('armed')

    def _update_primary(self):
        self._primary.set_sensitive(bool(self._name.get_text().strip()))

    def _focus(self, widget):
        widget.grab_focus()
        widget.set_position(-1)
        return GLib.SOURCE_REMOVE

    # -- actions -----------------------------------------------------------

    def _save(self):
        if not self._primary.get_sensitive():
            return  # Enter in an empty name field
        # Saved is what has arrived; the rest is not waited for.
        self.stop_loading()
        buffer = self._description.get_buffer()
        executable = self._executable.get_text()
        if executable.startswith('~'):
            executable = os.path.expanduser(executable)
        fields = {
            'name': self._name.get_text().strip(),
            'description': buffer.get_text(buffer.get_start_iter(),
                                           buffer.get_end_iter(), False),
            'version': self._version.get_text(),
            'executable': executable,
        }
        # For a new game every image is a change: there is nothing on disk
        # yet. That also holds when a first Save added the game but failed
        # on its images, and this is the second.
        changed = self._pictures_changed or self._game is None
        self._on_save(fields, list(self._pictures), changed)

    def _on_delete_clicked(self, button):
        if not self._armed:
            # The first click only asks: a game and all its images are not
            # gone after one slip of the mouse.
            self._armed = True
            button.set_label(_('Click again to delete'))
            button.add_css_class('armed')
            return
        self._on_delete()

    def _on_browse(self, _button):
        chooser = Gtk.FileDialog(title=_('Choose the launcher'), modal=True)
        typed = os.path.expanduser(self._executable.get_text().strip())
        current = Path(typed)
        if typed and current.is_absolute() and current.parent.is_dir():
            folder = current.parent
        else:
            # Nothing usable typed yet: not the working directory, which is
            # wherever Handcrafted happened to be started from.
            games = Path.home() / 'Games'
            folder = games if games.is_dir() else Path.home()
        chooser.set_initial_folder(Gio.File.new_for_path(str(folder)))
        chooser.open(self.get_root(), None, self._on_browsed)

    def _on_browsed(self, chooser, result):
        try:
            chosen = chooser.open_finish(result)
        except GLib.Error:
            return  # cancelled
        if chosen is not None and chosen.get_path():
            self._executable.set_text(chosen.get_path())

    def _on_key(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self._on_cancel()
            return True
        return False


def _shorten(url):
    '''Long links shortened in the middle, where they say the least.'''
    if len(url) <= SHOWN_URL:
        return url
    head = SHOWN_URL // 2 - 1
    return f'{url[:head]}…{url[-(SHOWN_URL - head - 1):]}'
