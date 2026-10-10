'''The main window: the hero on top, the library -- rail and detail side by
side -- below it, and the dialog laid over both when a game is added or
edited.

There is a hero only once something has been played; until then the window
is the library alone. Moving between the two by scrolling comes in phase 8;
for now Details goes down and the rail's "↑ Hero" back up.
'''

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import config, download, images, state  # noqa: E402
from .detail import Detail  # noqa: E402
from .hero import Hero  # noqa: E402
from .dialog import GameDialog  # noqa: E402
from .i18n import _  # noqa: E402
from .launch import LaunchError  # noqa: E402
from .library import recent  # noqa: E402
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
        self._dialog_folder = None  # where its downloads wait until Save
        self._hero_drawing = None  # what the hero shows once it is in view

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

        self._rail = Rail(on_select=self.select,
                          on_add=lambda: self.open_editor(None),
                          on_hero=self.show_hero)
        self._detail = Detail(
            on_play=self._on_play,
            on_edit=self.open_editor,
            on_fix_path=lambda game_id: self.open_editor(
                game_id, focus='executable'))
        body = Gtk.Box()
        body.append(self._rail)
        body.append(self._detail)
        self._hero_page = Hero(on_play=self._on_play,
                               on_details=self._on_details,
                               on_choose=self.choose_hero)
        # Hero first: SLIDE_UP_DOWN goes by the order of the pages, so the
        # library comes up from below.
        self._pages = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_UP_DOWN,
            transition_duration=450)
        self._pages.add_named(self._hero_page, 'hero')
        self._pages.add_named(body, 'library')
        # The dialog is not a window of its own: Adw.Dialog only stays inside
        # an Adw window, and this one is a plain GTK window for the sake of
        # the desktop's title bar. So it is laid over the pages instead.
        self._overlay = Gtk.Overlay()
        self._overlay.set_child(self._pages)
        self.set_child(self._overlay)

        self._selected = self._first_selection()
        self._hero = self._state['hero']  # checked against recent() below
        launcher.connect(self.refresh)
        self.connect('close-request', self._on_close_request)
        self.refresh()
        # Opens on the hero if there is one; no slide on the way in.
        self._pages.set_visible_child_full(
            'hero' if self._hero is not None else 'library',
            Gtk.StackTransitionType.NONE)

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

    def choose_hero(self, game_id):
        '''A tile was clicked: that game is the hero now, and nothing else
        changes -- not even an error shown for another game.'''
        self._hero = game_id
        self.refresh()

    def show_hero(self):
        if self._hero is not None:
            self._draw_hero()
            self._pages.set_visible_child_name('hero')

    def show_library(self):
        self._pages.set_visible_child_name('library')

    @property
    def page(self):
        '''`hero` or `library`, whichever is shown.'''
        return self._pages.get_visible_child_name()

    def refresh(self):
        '''Bring every view in line with the library. One read of it, and
        each view draws again only what changed: the rail moves its mark
        when only the selection did, the detail column and the hero do
        nothing when their game is as they last drew it, and the hero,
        while out of view, not even that.'''
        games = self._library.games()
        by_id = {game.id: game for game in games}
        if self._selected not in by_id:
            self._selected = games[0].id if games else None
        running = self._launcher.running_game
        if running is None and self._asking is not None:
            # The game ended while the question was up: nothing left to warn
            # about.
            self._asking.cancel()
        game = by_id.get(self._selected)
        if game is not None:
            self._status.set_state(GLib.Variant('s', game.status))
        tiles = recent(games)
        if not any(tile.id == self._hero for tile in tiles):
            # Never chosen, or no longer among the last four: the one played
            # last. Nothing played at all: no hero.
            self._hero = tiles[0].id if tiles else None
        if self._hero is None and self.page == 'hero':
            self._pages.set_visible_child_name('library')

        self._rail.refresh(games, self._selected, running,
                           has_hero=self._hero is not None)
        self._detail.show(game, running, self._error_for(self._selected))
        self._hero_drawing = None
        if self._hero is not None:
            self._hero_drawing = (by_id[self._hero], tiles, running,
                                  self._error_for(self._hero))
            if self.page == 'hero':
                self._draw_hero()
        if self._dialog is not None:
            self._dialog.set_running(
                running is not None and running == self._dialog_game)

    def _draw_hero(self):
        if self._hero_drawing is not None:
            self._hero_page.show(*self._hero_drawing)

    def _error_for(self, game_id):
        if self._error is not None and self._error[0] == game_id:
            return self._error[1]
        return None

    # -- actions -----------------------------------------------------------

    def _on_play(self, game_id):
        if self._launcher.running_game == game_id:
            self._launcher.stop()
            return
        # Cleared first: launch() redraws everything as the game starts, and
        # an old failure must not stand next to "Running · Stop".
        self._error = None
        try:
            self._launcher.launch(game_id)
        except LaunchError as error:
            # Shown under the title, so a click on Play never does nothing.
            self._error = (game_id, str(error))
            self.refresh()

    def _on_details(self, game_id):
        # Not select(): that forgets why Play just failed, and Details is
        # where "Fix path…" is.
        self._selected = game_id
        self.refresh()
        self.show_library()

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
        try:
            self._dialog_folder = download.new_folder()
        except OSError:
            # No room in ~/.cache: the dialog still opens, only without the
            # link field.
            self._dialog_folder = None
        self._dialog = GameDialog(
            game, pictures,
            running=(game is not None
                     and self._launcher.running_game == game.id),
            on_save=self._save_editor, on_cancel=self.close_editor,
            on_delete=self._delete_from_editor, focus=focus,
            folder=self._dialog_folder)
        self._overlay.add_overlay(self._dialog)
        # The sheet covers the pages for the mouse; this does the same for
        # the keyboard, so Tab cannot wander into a Play button behind it.
        self._pages.set_can_focus(False)
        self._pages.set_can_target(False)
        self._pages.add_css_class('behind-dialog')

    def close_editor(self):
        if self._dialog is not None:
            self._dialog.stop_loading()
            self._overlay.remove_overlay(self._dialog)
            self._dialog = None
            self._dialog_game = None
            # Saved images were copied into the library by now; anything
            # else loaded for this dialog goes.
            download.remove_folder(self._dialog_folder)
            self._dialog_folder = None
            self._pages.set_can_focus(True)
            self._pages.set_can_target(True)
            self._pages.remove_css_class('behind-dialog')

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
        self.refresh()  # which selects another game, the one gone missing

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
                           selected=self._selected, hero=self._hero)
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
