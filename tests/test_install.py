'''install.py, into a throwaway home folder.

    /usr/bin/python3 tests/test_install.py

Never touches the real ~/.local: every path comes from install.Places,
pointed at a folder of its own here.
'''

import contextlib
import io
import shutil
import subprocess

from harness import check, report, sandbox, section

import install  # noqa: E402

folder = sandbox()
home = folder / 'home'
places = install.Places(home)


def quietly(function, *args, **kwargs):
    '''Run it with its progress report swallowed. Returns what it raised,
    if it stopped.'''
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            function(*args, **kwargs)
        except SystemExit as stop:
            return stop
    return None


def files_under(path):
    return sorted(str(p.relative_to(path)) for p in path.rglob('*')
                  if p.is_file())


# The library, as it would be after some use. None of it may ever go.
places.data.mkdir(parents=True)
(places.data / 'library.db').write_bytes(b'games')
(places.data / 'images' / '1').mkdir(parents=True)
(places.data / 'images' / '1' / '1.png').write_bytes(b'picture')
places.config.mkdir(parents=True)
(places.config / 'config.json').write_text('{}')

section('Installing')

check('GTK 4 and libadwaita load in the system Python',
      install.gtk_available())
stopped = quietly(install.install, places)
check('it runs through', stopped is None, stopped)
package = places.app / 'handcrafted'
check('the program is copied', (package / '__main__.py').is_file())
check('without compiled leftovers',
      not any('__pycache__' in p for p in files_under(package)))
check('with its icon and stylesheet',
      (package / 'style.css').is_file()
      and (package / 'icons' / f'{install.APP_ID}.svg').is_file())
mo = places.app / 'locale' / 'de' / 'LC_MESSAGES' / 'handcrafted.mo'
if shutil.which('msgfmt'):
    check('the German catalogue is built where i18n looks for it',
          mo.is_file(), files_under(places.app / 'locale'))
check('the icon is in the icon theme', places.icon.is_file())
entry = places.desktop.read_text(encoding='utf-8')
check('the menu entry runs the copy with the system Python',
      f'Exec=env "PYTHONPATH={places.app}" /usr/bin/python3 -m handcrafted'
      in entry, entry)
check('finding it whether or not the desktop honours Path=',
      f'Path={places.app}' in entry)
check('names the icon and the window class',
      f'Icon={install.APP_ID}' in entry
      and 'StartupWMClass=handcrafted' in entry)
if shutil.which('desktop-file-validate'):
    result = subprocess.run(['desktop-file-validate', str(places.desktop)],
                            capture_output=True, text=True)
    check('and is a valid desktop entry',
          result.returncode == 0 and not result.stdout.strip(),
          result.stdout)

if mo.is_file():
    said = subprocess.run(
        [install.PYTHON, '-c',
         'from handcrafted import i18n; i18n.setup("de"); '
         'print(i18n._("Library"))'],
        cwd=places.app, capture_output=True, text=True).stdout.strip()
    check('the installed copy speaks German', said == 'Bibliothek', said)

section('Installing again')

(package / 'gone.py').write_text('# dropped from the project since')
stopped = quietly(install.install, places)
check('works', stopped is None, stopped)
check('and leaves nothing of the old copy behind',
      not (package / 'gone.py').exists())

section('Something else in the way')

stranger = install.Places(folder / 'other-home')
(stranger.app / 'handcrafted').mkdir(parents=True)
(stranger.app / 'handcrafted' / 'notes.txt').write_text('mine')
stopped = quietly(install.install, stranger)
check('a folder that is not ours is refused', stopped is not None)
check('and left as it was',
      (stranger.app / 'handcrafted' / 'notes.txt').read_text() == 'mine')
stopped = quietly(install.uninstall, stranger)
check('uninstalling will not take it either',
      stopped is not None
      and (stranger.app / 'handcrafted' / 'notes.txt').exists())

section('A catalogue that does not compile')

# A copy of the repository to break, rather than the repository itself.
repository = folder / 'repository'
for part in ('handcrafted', 'po'):
    shutil.copytree(install.HERE / part, repository / part,
                    ignore=shutil.ignore_patterns('__pycache__'))
real_here = install.HERE
install.HERE = repository
if shutil.which('msgfmt'):
    good = (repository / 'po' / 'de.po').read_text(encoding='utf-8')
    (repository / 'po' / 'de.po').write_text(
        good.replace('msgstr "Bibliothek"', 'msgstr "Bibliothek'),
        encoding='utf-8')
    before = files_under(places.app)
    stopped = quietly(install.install, places)
    check('stops with a reason', stopped is not None
          and 'de.po' in str(stopped.code), stopped)
    check('before anything was changed', files_under(places.app) == before)
    (repository / 'po' / 'de.po').write_text(good, encoding='utf-8')

section('In place')

stopped = quietly(install.install, places, in_place=True)
check('runs through', stopped is None, stopped)
entry = places.desktop.read_text(encoding='utf-8')
check('the menu entry runs the repository',
      f'Path={repository}\n' in entry, entry)
if shutil.which('msgfmt'):
    check('with the catalogue built there',
          (repository / 'locale' / 'de' / 'LC_MESSAGES'
           / 'handcrafted.mo').is_file())
install.HERE = real_here

section('Uninstalling')

quietly(install.install, places)
(places.app / 'notes.txt').write_text('put here by hand')
stopped = quietly(install.uninstall, places)
check('runs through', stopped is None, stopped)
check('the program is gone',
      not (places.app / 'handcrafted').exists()
      and not (places.app / 'locale').exists())
check('but nothing it did not put there',
      (places.app / 'notes.txt').read_text() == 'put here by hand')
(places.app / 'notes.txt').unlink()
quietly(install.uninstall, places)
check('an emptied folder goes as well', not places.app.exists())
check('the menu entry and the icon too',
      not places.desktop.exists() and not places.icon.exists())
check('the library stays',
      (places.data / 'library.db').read_bytes() == b'games'
      and (places.data / 'images' / '1' / '1.png').is_file())
check('and so do the settings', (places.config / 'config.json').is_file())
stopped = quietly(install.uninstall, places)
check('uninstalling twice is no error', stopped is None, stopped)

section('A path a menu entry cannot carry')

odd = install.Places(folder / 'odd$home')
stopped = quietly(install.install, odd)
check('is refused with a reason', stopped is not None
      and 'cannot carry safely' in str(stopped.code), stopped)
check('before anything was written', not odd.app.exists()
      and not odd.desktop.exists())

section('A link in the way')

linked = install.Places(folder / 'linked-home')
linked.app.mkdir(parents=True)
(linked.app / 'handcrafted').symlink_to(install.HERE / 'handcrafted')
stopped = quietly(install.install, linked)
check('a symlinked package is refused, not emptied through the link',
      stopped is not None
      and (install.HERE / 'handcrafted' / '__main__.py').is_file())

report(folder)
