'''Entry point.

Run it from the repository:

    /usr/bin/python3 -m handcrafted

Note the interpreter. A plain `python3` may well be a conda or miniforge
build, and those do not ship the `gi` bindings -- the failure looks like
`ModuleNotFoundError: No module named 'gi'` and has nothing to do with
Handcrafted.
'''

import sys

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GLib  # noqa: E402


def main(argv=None):
    argv = sys.argv if argv is None else argv

    # Both before the first window exists: the program name ends up in
    # WM_CLASS, which the desktop entry will have to match in phase 9.
    from . import config
    GLib.set_prgname(config.PRG_NAME)
    GLib.set_application_name(config.APP_NAME)

    from .application import HandcraftedApplication
    app = HandcraftedApplication()
    return app.run(argv)


if __name__ == '__main__':
    sys.exit(main())
