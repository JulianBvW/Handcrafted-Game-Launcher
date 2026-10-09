# Handcrafted

A game launcher for a library you keep by hand.

No VNDB, no Steam, no metadata pulled from anywhere. Every game is entered
by hand: a name, a line or two of description, the path to its launcher, and
a list of image links. That is where the name comes from.

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
