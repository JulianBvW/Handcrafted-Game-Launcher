'''The library: entries, sessions, groups.

    /usr/bin/python3 tests/test_library.py
'''

import sqlite3

from harness import check, report, sandbox, section

from handcrafted import config
from handcrafted.library import Library

folder = sandbox()
DAY = 86400
T0 = 1_780_000_000  # some afternoon in 2026


def raises(error, function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except error:
        return True
    return False


section('Opening')

library = Library()
check('the file lands under data_dir', config.LIBRARY_FILE.exists(),
      str(config.LIBRARY_FILE))
version = library._db.execute('PRAGMA user_version').fetchone()[0]
check('schema version is 1', version == 1, version)
check('an empty library has no games', library.games() == [])
check('and totals of nothing', library.totals() == (0, 0))

section('Adding')

check('an empty name is refused', raises(ValueError, library.add, '   '))
check('a missing name is refused', raises(ValueError, library.add, None))

kettle = library.add('  Kettle Summer ', 'A café.',
                     '/games/kettle-1.2/run.sh', '1.2', now=T0)
game = library.get(kettle)
check('the name is trimmed', game.name == 'Kettle Summer', game.name)
check('a new game is new', game.status == 'new', game.status)
check('with no playtime', game.playtime == 0)
check('and never played', game.last_played is None)
check('added is stamped', game.added == T0, game.added)
check('get of an unknown id is None', library.get(9999) is None)

section('The identity is the entry (DESIGN 2.2)')

session = library.start_session(kettle, now=T0 + DAY)
library.end_session(session, 4000, 0, now=T0 + DAY + 4000)
before = library.get(kettle)
library.update(kettle, executable='/games/kettle-1.3/run.sh', version='1.3')
after = library.get(kettle)
check('the new path is stored',
      after.executable == '/games/kettle-1.3/run.sh', after.executable)
check('playtime survives a new path',
      after.playtime == before.playtime == 4000,
      f'{before.playtime} -> {after.playtime}')
check('status survives a new path', after.status == before.status)
check('last played survives a new path',
      after.last_played == before.last_played)
check('added survives a new path', after.added == before.added)

check('playtime cannot be edited',
      raises(ValueError, library.update, kettle, playtime=0))
check('added cannot be edited',
      raises(ValueError, library.update, kettle, added=0))
check('an unknown status is refused',
      raises(ValueError, library.set_status, kettle, 'paused'))
check('a blank name is refused on update',
      raises(ValueError, library.update, kettle, name=''))
check('a number is not a description',
      raises(ValueError, library.update, kettle, description=5))
check('updating a game that is gone says so',
      raises(KeyError, library.update, 9999, name='Ghost'))
check('nothing changed after the refusals',
      library.get(kettle) == after)

spaced = library.add('Spaced', executable='/games/odd name /run.sh ')
check('a path is stored exactly as given',
      library.get(spaced).executable == '/games/odd name /run.sh ',
      repr(library.get(spaced).executable))
library.delete(spaced)

library.add('Twin', executable='/games/kettle-1.3/run.sh', now=T0)
check('the same path twice is two entries',
      sum(g.executable == '/games/kettle-1.3/run.sh'
          for g in library.games()) == 2)

section('Sessions')

fresh = library.add('Fresh', now=T0)
session = library.start_session(fresh, now=T0 + 2 * DAY)
check('starting moves new to playing',
      library.get(fresh).status == 'playing')
check('starting stamps last played',
      library.get(fresh).last_played == T0 + 2 * DAY)
library.end_session(session, 5.7, 0)
check('a five-second session counts as a minute',
      library.get(fresh).playtime == 60, library.get(fresh).playtime)
library.end_session(session, 5000, 0)
check('ending the same session twice counts once',
      library.get(fresh).playtime == 60, library.get(fresh).playtime)

session = library.start_session(fresh, now=T0 + 3 * DAY)
library.end_session(session, 3700.9, 1)
check('a long session adds its whole seconds',
      library.get(fresh).playtime == 3760, library.get(fresh).playtime)
row = library._db.execute('SELECT * FROM sessions WHERE id = ?',
                          (session,)).fetchone()
check('the session keeps its exit code and seconds',
      (row['exit_code'], row['seconds']) == (1, 3700), dict(row))

library.set_status(fresh, 'done')
session = library.start_session(fresh, now=T0 + 4 * DAY)
check('starting a done game leaves it done',
      library.get(fresh).status == 'done')

open_count = library._db.execute(
    'SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL').fetchone()[0]
check('that session is open', open_count == 1, open_count)
playtime_before = library.get(fresh).playtime
library.close()

library = Library()
open_count = library._db.execute(
    'SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL').fetchone()[0]
check('opening alone leaves an open session alone', open_count == 1,
      open_count)
check('discarding at program start drops it',
      library.discard_open_sessions() == 1)
check('without touching the playtime',
      library.get(fresh).playtime == playtime_before)
check('the closed sessions stay', library._db.execute(
    'SELECT COUNT(*) FROM sessions WHERE game_id = ?', (fresh,)
).fetchone()[0] == 2)

section('Groups and order')

library.close()
config.LIBRARY_FILE.unlink()
library = Library()

a = library.add('A', now=T0)                 # new, added first
b = library.add('B', now=T0 + DAY)           # new, added later
c = library.add('C', now=T0)                 # played long ago
d = library.add('D', now=T0)                 # played recently
e = library.add('E', now=T0 + 5 * DAY)       # abandoned
for game_id, when in ((c, T0 + 2 * DAY), (d, T0 + 9 * DAY)):
    s = library.start_session(game_id, now=when)
    library.end_session(s, 600, 0)
library.set_status(e, 'abandoned')

groups = [(status, [g.name for g in games])
          for status, games in library.grouped()]
check('grouped in the order new, playing, abandoned; done is empty',
      groups == [('new', ['B', 'A']), ('playing', ['D', 'C']),
                 ('abandoned', ['E'])], groups)

groups = [(status, [g.name for g in games])
          for status, games in library.grouped(only_playing=True)]
check('only playing', groups == [('playing', ['D', 'C'])], groups)

check('recent leaves out the never played',
      [g.name for g in library.recent()] == ['D', 'C'])
check('recent respects the limit',
      [g.name for g in library.recent(limit=1)] == ['D'])
check('totals count every game and sum their time',
      library.totals() == (5, 1200), library.totals())

section('Deleting')

library.delete(d)
check('the game is gone', library.get(d) is None)
check('its sessions went with it', library._db.execute(
    'SELECT COUNT(*) FROM sessions WHERE game_id = ?', (d,)
).fetchone()[0] == 0)
newest = library.add('F', now=T0)
check('a deleted id is not handed out again', newest > e, f'{newest} vs {e}')

check('a session for an unknown game is refused',
      raises(sqlite3.IntegrityError, library.start_session, 9999))

section('A schema that was never finished')

library.close()
half = folder / 'half.db'
raw = sqlite3.connect(half)
raw.execute('BEGIN')
raw.execute('CREATE TABLE games (id INTEGER)')
raw.close()  # dies before COMMIT
try:
    rebuilt = Library(half)
    rebuilt.add('Works')
    check('a crash while building leaves a file that still opens', True)
    rebuilt.close()
except sqlite3.Error as error:
    check('a crash while building leaves a file that still opens', False,
          error)
library = Library()

section('A newer schema')

library._db.execute('PRAGMA user_version = 2')
library._db.commit()
library.close()
check('a library from a newer program is refused, not overwritten',
      raises(RuntimeError, Library))

report(folder)
