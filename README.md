# Handcrafted

A game launcher for a library you keep by hand.

No VNDB, no Steam, no metadata pulled from anywhere. Every game is entered
by hand: a name, a line or two of description, the path to its launcher, and
a list of image links. That is where the name comes from.

## Status

In development. The library view works: games grouped by status, their
details, Play and Stop with the time measured. Adding and editing games
from the interface comes next.

To look at it without a library of your own, fill a throwaway one:

```
HOME=/tmp/hc-demo /usr/bin/python3 tests/seed.py
HOME=/tmp/hc-demo /usr/bin/python3 -m handcrafted
```

## Requirements

Linux, Python 3, GTK 4 and libadwaita, via the system interpreter:

```
sudo apt install gir1.2-gtk-4.0 gir1.2-adw-1
```

Use `/usr/bin/python3`, not `python3`. On a machine with conda or miniforge
in the PATH, the latter has no `gi`.

## Run

From the repository:

```
/usr/bin/python3 -m handcrafted
```

Starting it a second time brings the open window to the front.

The library lives in `~/.local/share/handcrafted/`, the window size in
`~/.config/handcrafted/state.json`. A few things can be set in
`~/.config/handcrafted/config.json`:

```json
{
  "width": 1600,
  "height": 900,
  "data_dir": "~/.local/share/handcrafted",
  "language": "en"
}
```

`language` picks the interface language; without it, the system's is
used. `width` and `height` are the size of the very first window. After
that, the size it was last left at wins. A missing, broken or half-wrong
file is not an error: whatever cannot be used is ignored.

## Tests

No test runner to install. Run each file directly:

```
/usr/bin/python3 tests/test_config.py       # the settings file
/usr/bin/python3 tests/test_state.py        # the remembered window size
/usr/bin/python3 tests/test_library.py      # games and play sessions
/usr/bin/python3 tests/test_images.py       # images on disk
/usr/bin/python3 tests/test_formatting.py   # playtime and dates as text
/usr/bin/python3 tests/test_launch.py       # starting and timing games
DISPLAY=:0 /usr/bin/python3 tests/test_window.py   # the library view
```

## What it will not do

No online sources of any kind. No Wine or Proton. No importing of Steam,
Lutris or Heroic libraries. No settings window: what can be configured lives
in a file. No sync, no cloud, no second user.

## Licence

MIT. See [LICENSE](LICENSE).
