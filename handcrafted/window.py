'''The main window: for now the library, rail and detail side by side,
and the dialog laid over them when a game is added or edited.

The hero above it arrives in phase 7.
'''

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import config, images, state  # noqa: E402
from .detail import Detail  # noqa: E402
from .dialog import GameDialog  # noqa: E402
from .i18n import _  # noqa: E402
from .launch import LaunchError  # noqa: E402
from .rail import Rail  # noqa: E402


class HandcraftedWindow(Gtk.ApplicationWindow):
    '''A plain GTK window rather than an Adw.ApplicationWindow.

    The design wants the desktop's own title bar and no header bar of ours.
    An Adw window draws no title bar at all unless it is given one; a GTK
    window without set_titlebar() is decorated by the window manager.
    '''

    def __init__(self, library, launcher, **kwargs):
        super().__init__(title=config.APP_NAME, **kwargs)
        self.add_css_class('handcrafted')
        self._library = library
        self._launcher = launcher
        self._closing = False
        self._asking = None     # a Gio.Cancellable while the question is up
        self._error = None      # (game_id, why) when Play just failed
        self._dialog = None     # the GameDialog while it is open
        self._dialog_game = None  # the id it edits; None when adding

        self._state = state.load()
        self.set_default_size(self._state['width'], self._state['height'])
        self.set_size_request(config.MIN_WIDTH, config.MIN_HEIGHT)
        if self._state['maximized']:
            self.maximize()

        # The status menu in the detail column acts through this. Stateful,
        # so the menu shows which status the game has.
        self._status = Gio.SimpleAction.new_stateful(
            'status', GLib.VariantType.new('s'), GLib.Variant('s', 'new'))
        self._status.connect('change-state', self._on_status)
        self.add_action(self._status)

        self._rail = Rail(library, on_select=self.select,
                          on_add=lambda: self.open_editor(None))
        self._detail = Detail(
            on_play=self._on_play,
            on_edit=self.open_editor,
            on_fix_path=lambda game_id: self.open_editor(
                game_id, focus='executable'))
        self._body = body = Gtk.Box()
        body.append(self._rail)
        body.append(self._detail)
        # The dialog is not a window of its own: Adw.Dialog only stays inside
        # an Adw window, and this one is a plain GTK window for the sake of
        # the desktop's title bar. So it is laid over the body instead.
        self._overlay = Gtk.Overlay()
        self._overlay.set_child(body)
        self.set_child(self._overlay)

        self._selected = self._first_selection()
        launcher.connect(self.refresh)
        self.connect('close-request', self._on_close_request)
        self.refresh()

    # -- selection and drawing ---------------------------------------------

    def _first_selection(self):
        '''The game selected last time, if it still exists, else the most
        recently active one, else nothing.'''
        remembered = self._state['selected']
        if remembered is not None and self._library.get(remembered):
            return remembered
        return self._most_recent()

    def _most_recent(self):
        games = self._library.games()
        return games[0].id if games else None

    def select(self, game_id):
        self._selected = game_id
        self._error = None
        self.refresh()

    def refresh(self):
        '''Draw everything again from the library. Cheap enough for a
        hand-kept collection, and never out of step.'''
        if self._selected is not None and not self._library.get(
                self._selected):
            self._selected = self._most_recent()
        running = self._launcher.running_game
        if running is None and self._asking is not None:
            # The game ended while the question was up: nothing left to warn
            # about.
            self._asking.cancel()
        game = (self._library.get(self._selected)
                if self._selected is not None else None)
        if game is not None:
            self._status.set_state(GLib.Variant('s', game.status))
        error = None
        if self._error is not None and self._error[0] == self._selected:
            error = self._error[1]
        self._rail.refresh(self._selected, running)
        self._detail.show(game, running, error)
        if self._dialog is not None:
            self._dialog.set_running(
                running is not None and running == self._dialog_game)

    # -- actions -----------------------------------------------------------

    def _on_play(self, game_id):
        if self._launcher.running_game == game_id:
            self._launcher.stop()
            return
        try:
            self._launcher.launch(game_id)
            self._error = None
        except LaunchError as error:
            # Shown under the title, so a click on Play never does nothing.
            self._error = (game_id, str(error))
            self.refresh()

    def _on_status(self, action, value):
        if self._selected is None:
            return
        self._library.set_status(self._selected, value.get_string())
        action.set_state(value)
        # Later, not now: the menu that called this is still closing, and
        # refresh() replaces it.
        GLib.idle_add(self._refresh_once)

    def _refresh_once(self):
        self.refresh()
        return GLib.SOURCE_REMOVE

    # -- the dialog --------------------------------------------------------

    def open_editor(self, game_id, focus='name'):
        '''"New game" with no id, "Edit game" with one.'''
        if self._dialog is not None:
            return
        game = self._library.get(game_id) if game_id is not None else None
        if game_id is not None and game is None:
            self.refresh()  # gone meanwhile: not a reason for "New game"
            return
        pictures = images.listing(game_id) if game is not None else []
        self._dialog_game = game_id
        self._dialog = GameDialog(
            game, pictures,
            running=(game is not None
                     and self._launcher.running_game == game.id),
            on_save=self._save_editor, on_cancel=self.close_editor,
            on_delete=self._delete_from_editor, focus=focus)
        self._overlay.add_overlay(self._dialog)
        # The sheet covers the library for the mouse; this does the same for
        # the keyboard, so Tab cannot wander into a Play button behind it.
        self._body.set_can_focus(False)
        self._body.set_can_target(False)

    def close_editor(self):
        if self._dialog is not None:
            self._overlay.remove_overlay(self._dialog)
            self._dialog = None
            self._dialog_game = None
            self._body.set_can_focus(True)
            self._body.set_can_target(True)

    def _save_editor(self, fields, pictures, pictures_changed):
        if self._dialog is None:
            return  # a click that arrived after the dialog closed
        game_id = self._dialog_game
        try:
            if game_id is None:
                game_id = self._library.add(**fields)
                # From here on the dialog edits the game it just added, so
                # a second Save after a failure below cannot add it twice.
                self._dialog_game = game_id
            else:
                # Only what a person edits. Playtime, status and the dates
                # are not in `fields` and could not be changed here if they
                # were.
                self._library.update(game_id, **fields)
            if pictures_changed:
                images.replace(game_id, pictures)
        except KeyError:
            # Deleted while the dialog was open: nothing left to save to.
            self.close_editor()
            self.refresh()
            return
        except OSError as error:
            self._dialog.show_error(
                _('Could not save the images: {reason}').format(
                    reason=error.strerror or error))
            return
        self.close_editor()
        self.select(game_id)

    def _delete_from_editor(self):
        game_id = self._dialog_game
        if game_id is None or self._launcher.running_game == game_id:
            return
        self._library.delete(game_id)
        images.remove(game_id)
        self.close_editor()
        self._selected = self._most_recent()
        self.refresh()

    # -- closing -----------------------------------------------------------

    def close_now(self):
        '''Close without asking, as on logout or Ctrl+C.'''
        self._closing = True
        self.close()

    def _on_close_request(self, _window):
        if self._launcher.running_game is not None and not self._closing:
            if self._asking is None:  # one question, however often asked
                self._ask_before_closing()
            return True  # not yet

        # In GTK 4 the default size follows the user's resizing but not a
        # maximize, so this is the size to come back to after unmaximizing.
        width, height = self.get_default_size()
        self._state.update(width=width, height=height,
                           maximized=self.is_maximized(),
                           selected=self._selected)
        state.save(self._state)
        return False

    def _ask_before_closing(self):
        dialog = Gtk.AlertDialog(
            message=_('A game is still running'),
            detail=_('Its playtime will not be counted if Handcrafted '
                     'closes now.'),
            buttons=[_('Keep open'), _('Close anyway')],
            cancel_button=0, default_button=0, modal=True)
        self._asking = Gio.Cancellable()
        dialog.choose(self, self._asking, self._on_close_answer)

    def _on_close_answer(self, dialog, result):
        self._asking = None
        try:
            choice = dialog.choose_finish(result)
        except GLib.Error:
            return  # dismissed, or withdrawn because the game ended
        if choice == 1:
            self.close_now()
