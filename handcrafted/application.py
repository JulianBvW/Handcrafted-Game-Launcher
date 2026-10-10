'''The application object: one instance, one window.'''

import signal

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from . import config  # noqa: E402
from .launch import Launcher  # noqa: E402
from .library import Library  # noqa: E402
from .window import HandcraftedWindow  # noqa: E402


class HandcraftedApplication(Adw.Application):
    '''Unique on the session bus: starting it a second time brings the
    window that is already open to the front instead of opening another.'''

    def __init__(self):
        super().__init__(application_id=config.APP_ID)
        self.window = None
        self.library = None
        self.launcher = None

    def do_startup(self):
        Adw.Application.do_startup(self)

        # The design is dark whatever the desktop theme says. Without this
        # Mint-Y would paint light popovers and menus over it.
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_DARK)

        provider = Gtk.CssProvider()
        provider.load_from_path(str(config.STYLE_FILE))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.library = Library()
        # Once, here and nowhere else: a session still open at this moment
        # belongs to a run that ended while a game was being played --
        # crashed, or closed on purpose without counting the time.
        self.library.discard_open_sessions()
        self.launcher = Launcher(self.library, GLib.idle_add)

        # Logging out sends SIGTERM, Ctrl+C in the terminal SIGINT, closing
        # that terminal SIGHUP -- and Python would die on the spot at each.
        # Routed through the main loop instead, so the window still gets to
        # write down its size on the way out.
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum,
                                 self._on_signal)

    def do_shutdown(self):
        if self.library is not None:
            self.library.close()
        Adw.Application.do_shutdown(self)

    def do_activate(self):
        if self.window is None:
            self.window = HandcraftedWindow(
                self.library, self.launcher, application=self)
        self.window.present()

    def _on_signal(self):
        if self.window is not None:
            # No question asked: at logout nobody is there to answer it.
            self.window.close_now()
        self.quit()
        return GLib.SOURCE_REMOVE
