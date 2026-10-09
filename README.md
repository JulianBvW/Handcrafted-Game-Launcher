# Handcrafted

A game launcher for a library you keep by hand.

No VNDB, no Steam, no metadata pulled from anywhere. Every game is entered
by hand: a name, a line or two of description, the path to its launcher, and
a list of image links. That is where the name comes from.

Built for a collection of Ren'Py visual novels that run natively on Linux,
each with a `.sh` launcher next to its `.exe`.

## Why

Two things that ready-made launchers get wrong or do not do at all:

**Playtime that is right.** Handcrafted measures how long the game's process
ran, not which process names it can find. Ren'Py's launcher `exec`s into the
game, so the process it starts *is* the game, and waiting for it is the whole
measurement. Suspend does not count, since the clock is monotonic. Pauses do
count: what happens inside the game cannot be seen from outside.

**Images as a list of links.** Paste a handful of URLs, press Load, and the
images are on disk. You don't download anything yourself, there is no file
picker and nothing to rename. The first image is the cover.

## Status

In development. Nothing to run yet.

## Requirements

Linux, Python 3, GTK 4 and libadwaita, via the system interpreter:

```
sudo apt install gir1.2-gtk-4.0 gir1.2-adw-1
```

Use `/usr/bin/python3`, not `python3`. On a machine with conda or miniforge
in the PATH, the latter has no `gi`.

## What it will not do

No online sources of any kind. No Wine or Proton. No importing of Steam,
Lutris or Heroic libraries. No settings window: what can be configured lives
in a file. No sync, no cloud, no second user.

## Licence

MIT. See [LICENSE](LICENSE).
