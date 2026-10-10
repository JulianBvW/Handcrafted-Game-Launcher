'''The main window. Empty for now; the library moves in with phase 4.'''

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa: E402

from . import config, state  # noqa: E402


class HandcraftedWindow(Gtk.ApplicationWindow):
    '''A plain GTK window rather than an Adw.ApplicationWindow.

    The design wants the desktop's own title bar and no header bar of ours.
    An Adw window draws no title bar at all unless it is given one; a GTK
    window without set_titlebar() is decorated by the window manager.
    '''

    def __init__(self, **kwargs):
        super().__init__(title=config.APP_NAME, **kwargs)
        self.add_css_class('handcrafted')

        remembered = state.load()
        self.set_default_size(remembered['width'], remembered['height'])
        self.set_size_request(config.MIN_WIDTH, config.MIN_HEIGHT)
        if remembered['maximized']:
            self.maximize()

        self.set_child(Gtk.Box())

        self.connect('close-request', self._on_close_request)

    def _on_close_request(self, _window):
        # In GTK 4 the default size follows the user's resizing but not a
        # maximize, so this is the size to come back to after unmaximizing.
        width, height = self.get_default_size()
        state.save(width, height, self.is_maximized())
        return False  # let it close
