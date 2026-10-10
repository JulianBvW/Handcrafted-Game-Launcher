# Handcrafted

A game launcher for a library you keep by hand.

No VNDB, no Steam, no metadata pulled from anywhere. Every game is entered
by hand: a name, a line or two of description, the path to its launcher, and
a few pictures. That is where the name comes from.

![The hero: the game played last, over the four most recent][shot]

[shot]: docs/screenshot.png

## Status

Complete for what it sets out to do: add, edit and delete games, give them
pictures from this computer or from links, see them grouped by status, play
and stop them with the time measured. Once something has been played, the
window opens on a hero with the game played last and the four most recent
as tiles. Scroll down to get from the hero to the library, and up again,
from the top of the list, to get back. In English and German.

To look at it without a library of your own, fill a throwaway one:

```
HOME=/tmp/hc-demo /usr/bin/python3 tests/seed.py
HOME=/tmp/hc-demo /usr/bin/python3 -m handcrafted
```

## Requirements

Linux, Python 3, GTK 4 and libadwaita, via the system interpreter:

```
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gettext
```

`gettext` is only needed to build the translations; without it, Handcrafted
installs in English.

Use `/usr/bin/python3`, not `python3`. On a machine with conda or miniforge
in the PATH, the latter has no `gi`.

## Install

```
/usr/bin/python3 install.py
```

This copies the program to `~/.local/share/handcrafted/app/`, builds the
translations, and puts Handcrafted and its icon into the desktop's menu.
It asks nothing, needs no root and touches nothing outside your home. Run
it again after pulling to update.

```
/usr/bin/python3 install.py --in-place    # the menu runs this repository
/usr/bin/python3 install.py --uninstall   # remove it again
```

`--uninstall` removes the program, the menu entry and the icon. Your
library, its images and your settings stay where they are.

## Run

From the menu once installed, or from the repository:

```
/usr/bin/python3 -m handcrafted
```

Starting it a second time brings the open window to the front.

The library lives in `~/.local/share/handcrafted/`; the window size, the
selected game and the hero in `~/.config/handcrafted/state.json`. A few
things can be set in `~/.config/handcrafted/config.json`:

```json
{
  "width": 1600,
  "height": 900,
  "data_dir": "~/.local/share/handcrafted",
  "language": "en"
}
```

`language` picks the interface language (`en` or `de`); without it, the
system's is used. Run from the repository, translations need building once
with `install.py --in-place`. `width` and `height` are the size of the very
first window. After that, the size it was last left at wins. A missing,
broken or half-wrong file is not an error: whatever cannot be used is
ignored.

## Keys

| Key | |
|---|---|
| Ctrl+N | add a game |
| Ctrl+E | edit the selected game (on the hero: the hero's) |
| Ctrl+Enter | play or stop it |
| Alt+Down, Alt+Up | from the hero to the library and back |
| Up, Down, Enter | move through the list and select |
| F11 | full screen |
| Escape | close the dialog, or the links sheet in it |

## Pictures

In the dialog, the tile with the plus at the end of the pictures adds more:
from this computer, through the usual file chooser, or from links, pasted
one per line. Either way each picture is checked before it is taken: a real
JPEG, PNG, WebP, GIF or AVIF, at most 20 MB and 64 megapixels. Nothing is
kept until Save; Cancel leaves the library as it was. The first picture is
the cover; click another to make it the cover. Animated GIFs play in the
game's gallery and in the dialog's preview, and stand still everywhere
else.

A long description shows five lines in the library, with "More" to unfold
it, and four in the hero, where Details has the rest.

## When it stutters

If moving between hero and library stutters, start it with
`HANDCRAFTED_DEBUG_FRAMES=1` in front: each change of page then prints how
long its frames took, which tells a slow program from a busy machine.

## Tests

No test runner to install. Run each file directly:

```
/usr/bin/python3 tests/test_config.py       # the settings file
/usr/bin/python3 tests/test_state.py        # what the window remembers
/usr/bin/python3 tests/test_library.py      # games and play sessions
/usr/bin/python3 tests/test_images.py       # images on disk
/usr/bin/python3 tests/test_formatting.py   # playtime and dates as text
/usr/bin/python3 tests/test_launch.py       # starting and timing games
/usr/bin/python3 tests/test_download.py     # images from links, locally
/usr/bin/python3 tests/test_paging.py       # when scrolling changes the page
/usr/bin/python3 tests/test_thumbs.py       # images read and kept
/usr/bin/python3 tests/test_translations.py # po/ complete and valid
/usr/bin/python3 tests/test_install.py      # install.py, in a throwaway home
DISPLAY=:0 /usr/bin/python3 tests/test_window.py   # the library view
DISPLAY=:0 /usr/bin/python3 tests/test_dialog.py   # adding and editing
DISPLAY=:0 /usr/bin/python3 tests/test_hero.py     # the hero and its tiles
```

## Translations

Texts are marked with `_()` in the code; English is the source. After
changing them, refresh the template and the German catalogue:

```
xgettext --language=Python --keyword=_ --keyword=ngettext:1,2 \
    --from-code=UTF-8 -o po/handcrafted.pot handcrafted/*.py
msgmerge --update --backup=none po/de.po po/handcrafted.pot
```

`tests/test_translations.py` fails while anything is left untranslated. A
new language is one more `po/<code>.po`.

## What it will not do

No online sources of any kind. No Wine or Proton. No importing of Steam,
Lutris or Heroic libraries. No settings window: what can be configured lives
in a file. No sync, no cloud, no second user.

## Licence

MIT. See [LICENSE](LICENSE).
