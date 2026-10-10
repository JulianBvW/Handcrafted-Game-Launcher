#!/usr/bin/python3
'''Put Handcrafted on this machine, or take it back off again.

    /usr/bin/python3 install.py               # copy it into ~/.local
    /usr/bin/python3 install.py --in-place    # run it from this repository
    /usr/bin/python3 install.py --uninstall

No questions: there is nothing to set up. Nothing outside the user's own
home is touched and nothing needs root. The library -- library.db, the
images, config.json -- is never touched either, not even by --uninstall.
'''

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# The names come from the program itself, so a renamed app id or gettext
# domain cannot leave the menu entry or the catalogues behind. Neither
# module needs GTK.
from handcrafted import config, i18n

HERE = Path(__file__).resolve().parent
PACKAGE = 'handcrafted'
APP_ID = config.APP_ID
PRG_NAME = config.PRG_NAME   # WM_CLASS, as __main__ sets it
DOMAIN = i18n.DOMAIN
PYTHON = '/usr/bin/python3'

DESKTOP_ENTRY = '''[Desktop Entry]
Type=Application
Name=Handcrafted
Comment=A game launcher for a library you keep by hand
Comment[de]=Ein Spiele-Launcher für eine Sammlung, die du von Hand pflegst
Exec=env "PYTHONPATH={path}" {python} -m {package}
Path={path}
Icon={app_id}
StartupWMClass={wm_class}
Terminal=false
Categories=Game;
Keywords=games;launcher;visual novel;
'''

GTK_CHECK = ('import gi; gi.require_version("Gtk", "4.0"); '
             'gi.require_version("Adw", "1"); '
             'from gi.repository import Adw, Gtk')


# -- where things go -------------------------------------------------------

class Places:
    '''Every path this script writes to, under one home folder, so the
    tests can point it at a throwaway one.'''

    def __init__(self, home):
        share = Path(home) / '.local' / 'share'
        self.data = share / 'handcrafted'              # the library: never touched
        self.app = self.data / 'app'                   # the installed program
        self.desktop = share / 'applications' / f'{APP_ID}.desktop'
        self.icons = share / 'icons' / 'hicolor'
        self.icon = self.icons / 'scalable' / 'apps' / f'{APP_ID}.svg'
        self.config = Path(home) / '.config' / 'handcrafted'


# -- the parts --------------------------------------------------------------

def gtk_available(python=PYTHON):
    '''Can the interpreter the menu entry runs load GTK 4 and libadwaita?
    On this machine `python3` in PATH is miniforge without gi; the failure
    would only show as a menu entry that does nothing.'''
    try:
        subprocess.run([python, '-c', GTK_CHECK], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def is_ours(folder):
    return (folder / '__main__.py').is_file() and (
        folder / 'application.py').is_file()


def copy_package(app_dir, source=None):
    '''The package into app_dir/handcrafted, replacing an earlier copy --
    but only one that is recognisably ours.'''
    source = HERE if source is None else source
    target = app_dir / PACKAGE
    if target.is_symlink() or (target.exists() and not is_ours(target)):
        raise SystemExit(f'{target} exists and is not a Handcrafted install. '
                         'Refusing to touch it.')
    try:
        # Emptied first, so files dropped from the project do not live on.
        if target.exists():
            shutil.rmtree(target)
        app_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source / PACKAGE, target,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    except OSError as error:
        raise SystemExit(f'Could not copy the program to {target}: '
                         f'{error.strerror or error}')
    return target


def build_translations(locale_dir, po_dir=None):
    '''Every po/<lang>.po as locale_dir/<lang>/LC_MESSAGES/handcrafted.mo,
    which is where i18n.LOCALE_DIR (the package's parent, then locale/)
    looks. Returns the languages built; none without msgfmt.

    Built aside first and only then put in place: a catalogue msgfmt
    refuses stops the install before anything was changed, and never
    leaves the program half updated behind the old menu entry.'''
    po_dir = HERE / 'po' if po_dir is None else po_dir
    if shutil.which('msgfmt') is None:
        return []
    staging = Path(tempfile.mkdtemp(prefix='handcrafted-locale-'))
    try:
        built = []
        for po in sorted(po_dir.glob('*.po')):
            messages = staging / po.stem / 'LC_MESSAGES'
            messages.mkdir(parents=True)
            result = subprocess.run(
                ['msgfmt', '--check', '-o', str(messages / f'{DOMAIN}.mo'),
                 str(po)], capture_output=True, text=True)
            if result.returncode != 0:
                raise SystemExit(f'{po.name} does not compile, nothing was '
                                 f'installed:\n{result.stderr.strip()}')
            built.append(po.stem)
        shutil.rmtree(locale_dir, ignore_errors=True)
        locale_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging), str(locale_dir))
        return built
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def install_icon(places):
    places.icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / PACKAGE / 'icons' / f'{APP_ID}.svg', places.icon)


def write_desktop_entry(places, run_from):
    places.desktop.parent.mkdir(parents=True, exist_ok=True)
    places.desktop.write_text(DESKTOP_ENTRY.format(
        python=PYTHON, package=PACKAGE, path=run_from, app_id=APP_ID,
        wm_class=PRG_NAME), encoding='utf-8')


def refresh_caches(places):
    '''Tell the desktop about the new entry and icon. Neither is needed for
    it to work in the end, so a missing tool or a failure is no error.'''
    commands = [['update-desktop-database', '-q',
                 str(places.desktop.parent)]]
    if (places.icons / 'icon-theme.cache').is_file():
        # Only where a cache is already kept: a stale cache would hide the
        # new icon, no cache at all does not.
        commands.append(['gtk-update-icon-cache', '-q', '-t', '-f',
                         str(places.icons)])
    for command in commands:
        if shutil.which(command[0]):
            subprocess.run(command, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)


# -- the commands -----------------------------------------------------------

def install(places, in_place=False):
    if not gtk_available():
        raise SystemExit(f'{PYTHON} cannot load GTK 4 and libadwaita.\n'
                         'On Mint: sudo apt install python3-gi '
                         'gir1.2-gtk-4.0 gir1.2-adw-1')

    run_from = HERE if in_place else places.app
    # Translations first: if one does not compile, nothing has changed yet.
    languages = build_translations(run_from / 'locale')
    if in_place:
        print(f'  Running from {run_from} (--in-place)')
    else:
        copy_package(places.app)
        print(f'  Copied the program to {places.app / PACKAGE}')
    if languages:
        print(f'  Translations: {", ".join(languages)}')
    else:
        print('  No msgfmt (sudo apt install gettext): English only')

    install_icon(places)
    print(f'  Icon {places.icon}')
    write_desktop_entry(places, run_from)
    print(f'  Menu entry {places.desktop}')
    refresh_caches(places)

    print('\n  Done. Start it from the menu; if it is running already, '
          'close it and start it again.\n')


def uninstall(places):
    removed = []
    for path in (places.desktop, places.icon):
        if path.exists():
            path.unlink()
            removed.append(path)
    # Only what install() put there, never the whole folder: app/ lies
    # inside the library's own data folder.
    package = places.app / PACKAGE
    if package.exists() or package.is_symlink():
        if package.is_symlink() or not is_ours(package):
            raise SystemExit(f'{package} is not a Handcrafted install. '
                             'Leaving it.')
        shutil.rmtree(package)
        removed.append(package)
    locale = places.app / 'locale'
    if locale.exists():
        shutil.rmtree(locale)
        removed.append(locale)
    try:
        places.app.rmdir()  # only if nothing else is in it
    except OSError:
        pass
    refresh_caches(places)

    for path in removed:
        print(f'  Removed {path}')
    if not removed:
        print('  Nothing was installed.')
    print(f'\n  Kept, for you to delete by hand if you want:\n'
          f'    {places.data}   (the library and its images)\n'
          f'    {places.config}   (settings and window size)\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install Handcrafted.')
    parser.add_argument('--in-place', action='store_true',
                        help='run from this repository instead of a copy')
    parser.add_argument('--uninstall', action='store_true',
                        help='remove the program, keep the library')
    args = parser.parse_args(argv)
    places = Places(Path.home())
    print('\nHandcrafted\n')
    if args.uninstall:
        uninstall(places)
    else:
        install(places, in_place=args.in_place)


if __name__ == '__main__':
    sys.exit(main())
