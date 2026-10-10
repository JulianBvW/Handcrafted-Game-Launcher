'''The library: games and their play sessions, in one SQLite file.

The identity is the entry, not the executable. Everything hangs off
games.id. The path to the launcher is an ordinary field that can change
with every new version of a game, and changing it resets nothing --
playtime, status, dates and images all stay where they are.

Free of GTK. Every call is meant to come from the main thread; the thread
that waits for a game hands its result back through GLib.idle_add.
'''

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from . import config

# In the order the library groups them.
STATUSES = ('new', 'playing', 'done', 'abandoned')

# A session that ends sooner still counts as one minute, so an accidental
# double start does not end up as a session of nothing.
MIN_SESSION_SECONDS = 60

SCHEMA_VERSION = 1

# AUTOINCREMENT on purpose: without it SQLite may hand the id of a deleted
# game to the next one, which could then inherit an image folder that was
# left behind.
SCHEMA = f'''
BEGIN;
CREATE TABLE games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    executable  TEXT NOT NULL DEFAULT '',
    version     TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'new'
                CHECK (status IN {STATUSES}),
    playtime    INTEGER NOT NULL DEFAULT 0,
    last_played INTEGER,
    added       INTEGER NOT NULL
);
CREATE TABLE sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    started_at  INTEGER NOT NULL,
    ended_at    INTEGER,
    seconds     INTEGER,
    exit_code   INTEGER
);
CREATE INDEX sessions_game ON sessions(game_id);
PRAGMA user_version = {SCHEMA_VERSION};
COMMIT;
'''

# The fields a person edits. playtime, last_played and added are measured
# or stamped, and no edit can touch them.
EDITABLE = ('name', 'description', 'executable', 'version', 'status')

# Most recently active first: last played, or added if never played.
ORDER = 'ORDER BY COALESCE(last_played, added) DESC, id DESC'


@dataclass(frozen=True)
class Game:
    '''One row of `games`. Timestamps are Unix seconds, playtime seconds.'''
    id: int
    name: str
    description: str
    executable: str
    version: str
    status: str
    playtime: int
    last_played: int | None
    added: int


class Library:

    def __init__(self, path=None):
        path = Path(config.LIBRARY_FILE if path is None else path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.execute('PRAGMA foreign_keys = ON')
        self._migrate()

    def _migrate(self):
        version = self._db.execute('PRAGMA user_version').fetchone()[0]
        if version > SCHEMA_VERSION:
            # Written by a newer Handcrafted. Better to refuse than to write
            # into a layout this one does not know.
            raise RuntimeError(f'library schema {version} is newer than '
                               f'this program ({SCHEMA_VERSION})')
        if version == 0:
            # One transaction, the version stamp included: a run that dies
            # halfway leaves an empty file at version 0, which simply gets
            # built again, rather than half a schema that never opens.
            self._db.executescript(SCHEMA)

    def close(self):
        self._db.close()

    # -- reading -----------------------------------------------------------

    def get(self, game_id):
        row = self._db.execute('SELECT * FROM games WHERE id = ?',
                               (game_id,)).fetchone()
        return None if row is None else Game(**row)

    def games(self):
        '''Every game, most recently active first.'''
        return [Game(**row)
                for row in self._db.execute(f'SELECT * FROM games {ORDER}')]

    # -- editing -----------------------------------------------------------

    def add(self, name, description='', executable='', version='',
            now=None):
        '''A new game, status `new`. Returns its id.'''
        name = _name(name)
        added = int(time.time() if now is None else now)
        with self._db:
            cursor = self._db.execute(
                'INSERT INTO games (name, description, executable, version, '
                'added) VALUES (?, ?, ?, ?, ?)',
                (name, _text(description), _text(executable, strip=False),
                 _text(version), added))
        return cursor.lastrowid

    def update(self, game_id, **fields):
        '''Change what a person can change, and nothing else.

        A new path to the executable is just a new value in one column: no
        reset, no recalculation.
        '''
        unknown = set(fields) - set(EDITABLE)
        if unknown:
            raise ValueError(f'not editable: {", ".join(sorted(unknown))}')
        if not fields:
            return
        values = {}
        for key, value in fields.items():
            if key == 'name':
                values[key] = _name(value)
            elif key == 'status':
                values[key] = _status(value)
            else:
                # A path is taken as given: a space at its end may be real.
                values[key] = _text(value, strip=key != 'executable')
        columns = ', '.join(f'{key} = ?' for key in values)
        with self._db:
            cursor = self._db.execute(
                f'UPDATE games SET {columns} WHERE id = ?',
                (*values.values(), game_id))
        if cursor.rowcount == 0:
            raise KeyError(f'no game {game_id}')

    def set_status(self, game_id, status):
        self.update(game_id, status=status)

    def delete(self, game_id):
        '''The game and its sessions. Its images are images.remove()'s job.'''
        with self._db:
            self._db.execute('DELETE FROM games WHERE id = ?', (game_id,))

    # -- sessions ----------------------------------------------------------

    def start_session(self, game_id, now=None):
        '''Write an open session and return its id.

        Written at the start rather than the end, so a run that dies while
        the game is being played leaves a session that is recognisably open
        instead of none at all. Starting a game also stamps last_played and
        moves `new` to `playing` -- and changes no other status.
        '''
        now = int(time.time() if now is None else now)
        with self._db:
            cursor = self._db.execute(
                'INSERT INTO sessions (game_id, started_at) VALUES (?, ?)',
                (game_id, now))
            self._db.execute(
                "UPDATE games SET last_played = ?, status = CASE status "
                "WHEN 'new' THEN 'playing' ELSE status END WHERE id = ?",
                (now, game_id))
        return cursor.lastrowid

    def end_session(self, session_id, seconds, exit_code, now=None):
        '''Close a session and add its time to the game's playtime.

        `seconds` comes from the monotonic clock and `now` from the wall
        clock. After a suspend the two disagree on purpose: sleep is not
        playtime.
        '''
        now = int(time.time() if now is None else now)
        seconds = max(MIN_SESSION_SECONDS, int(seconds))
        with self._db:
            cursor = self._db.execute(
                'UPDATE sessions SET ended_at = ?, seconds = ?, exit_code = ? '
                'WHERE id = ? AND ended_at IS NULL',
                (now, seconds, exit_code, session_id))
            if cursor.rowcount == 0:
                return  # unknown or already closed: never count twice
            self._db.execute(
                'UPDATE games SET playtime = playtime + ? WHERE id = '
                '(SELECT game_id FROM sessions WHERE id = ?)',
                (seconds, session_id))

    def discard_open_sessions(self):
        '''Drop every session without an end. Returns how many.

        Called once when the program starts, never later: at that moment an
        open session belongs to a run that died while a game was being
        played. Its time is unknown, so it goes, without asking. Called
        while a game runs, it would throw away that game's session.
        '''
        with self._db:
            cursor = self._db.execute(
                'DELETE FROM sessions WHERE ended_at IS NULL')
        return cursor.rowcount


def _name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('a game needs a name')
    return value.strip()


def _status(value):
    if value not in STATUSES:
        raise ValueError(f'unknown status: {value!r}')
    return value


def _text(value, strip=True):
    if not isinstance(value, str):
        raise ValueError(f'expected text, got {type(value).__name__}')
    return value.strip() if strip else value


# -- views of a list of games ------------------------------------------------
# Worked out from one games() rather than asked of the database each: the
# window draws the rail, the detail column and the hero from a single read.

def grouped(games, only_playing=False):
    '''[(status, [Game, ...]), ...] in the order New, Playing, Done,
    Abandoned, each group in the order of `games`. Empty groups are left
    out; with only_playing, so is every group but Playing.'''
    groups = {status: [] for status in STATUSES}
    for game in games:
        groups[game.status].append(game)
    return [(status, members) for status, members in groups.items()
            if members and (not only_playing or status == 'playing')]


def recent(games, limit=4):
    '''The games played most recently. Never-played ones are left out.'''
    played = [game for game in games if game.last_played is not None]
    played.sort(key=lambda game: (game.last_played, game.id), reverse=True)
    return played[:limit]


def totals(games):
    '''(number of games, total playtime in seconds)'''
    return len(games), sum(game.playtime for game in games)
