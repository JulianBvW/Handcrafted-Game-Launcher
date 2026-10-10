'''Starting games and timing them, with launchers made up for the purpose.

    /usr/bin/python3 tests/test_launch.py

Takes about ten seconds: the games here really run, for a second or two.
'''

import os
import queue
import time

from harness import check, report, sandbox, section

from handcrafted import launch
from handcrafted.launch import AlreadyRunning, LaunchError, Launcher, Runner
from handcrafted.library import Library

folder = sandbox()
games = folder / 'games'

# Stands in for GLib.idle_add: the waiting thread drops its result here and
# the main thread picks it up, so the library never leaves the main thread.
handed_over = queue.Queue()


def deliver(function, *args):
    handed_over.put((function, args))


def pump(timeout=10):
    '''Run the next delivery in this (the main) thread, as the main loop
    would. False if nothing arrived in time.'''
    try:
        function, args = handed_over.get(timeout=timeout)
    except queue.Empty:
        return False
    function(*args)
    return True


def launcher_script(name, body, executable=True, shebang=True):
    path = games / name / 'run.sh'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(('#!/bin/sh\n' if shebang else '') + body + '\n')
    path.chmod(0o755 if executable else 0o644)
    return path


def raises(error, function, *args):
    try:
        function(*args)
    except error:
        return True
    return False


section('check()')

valid = launcher_script('valid', 'exit 0')
check('an empty path is missing', launch.check('') == 'missing')
check('a path that is not there is missing',
      launch.check(games / 'nope.sh') == 'missing')
check('a folder is missing', launch.check(games) == 'missing')
plain = launcher_script('plain', 'exit 0', executable=False)
check('without the x bit it is not executable',
      launch.check(plain) == 'not executable')
check('a proper launcher is fine', launch.check(valid) is None)
check('a relative path is missing, not guessed at',
      launch.check(os.path.relpath(valid)) == 'missing')
check('so is a bare file name', launch.check('run.sh') == 'missing')

section('Runner: timing')

runner = Runner(deliver)
results = []

runner.start(launcher_script('exec', 'exec sleep 1.5'), results.append)
check('running while it runs', runner.running)
pump()
result = results.pop()
check('exec into the game: the time is the game\'s',
      1.4 <= result.seconds < 4, f'{result.seconds:.2f} s')
check('exit code 0', result.exit_code == 0, result.exit_code)
check('not stopped', result.stopped is False)
check('not running afterwards', not runner.running)

runner.start(launcher_script('three', 'exit 3'), results.append)
pump()
check('the exit code comes through', results.pop().exit_code == 3)

# A launcher that sends the game into the background and ends at once.
# Without waiting for the process group this would measure nothing.
runner.start(launcher_script('background', 'sleep 1.5 &\nexit 0'),
             results.append)
pump()
result = results.pop()
check('a game left running in the background is waited for',
      1.4 <= result.seconds < 4, f'{result.seconds:.2f} s')

section('Runner: stopping')

runner.start(launcher_script('long', 'exec sleep 30'), results.append)
group = runner._proc.pid
time.sleep(0.5)
began = time.monotonic()
runner.stop()
pump()
result = results.pop()
check('no process of the game is left', not launch._group_alive(group))
check('stop ends it quickly', time.monotonic() - began < 2,
      f'{time.monotonic() - began:.2f} s')
check('marked as stopped', result.stopped is True)
check('ended by SIGTERM', result.exit_code == -15, result.exit_code)
runner.stop()
check('stop with nothing running changes nothing', not runner.running)

section('Runner: refusing')

runner.start(launcher_script('two', 'exec sleep 1.5'), results.append)
check('a second start is refused',
      raises(AlreadyRunning, runner.start, valid, results.append))
check('and the first one keeps running', runner.running)
pump()
check('the first one ends normally', results.pop().exit_code == 0)

check('a missing launcher is refused',
      raises(LaunchError, runner.start, games / 'nope.sh', results.append))
check('a launcher without the x bit is refused',
      raises(LaunchError, runner.start, plain, results.append))
check('a script without a shebang is refused',
      raises(LaunchError, runner.start,
             launcher_script('noshebang', 'exit 0', shebang=False),
             results.append))
check('nothing is left running after a refusal', not runner.running)

spaced = launcher_script('odd name ', 'exit 0')
runner.start(spaced, results.append)
pump()
check('a path with spaces starts', results.pop().exit_code == 0)

section('Launcher: sessions in the library')

library = Library()
launcher = Launcher(library, deliver)
heard = []
launcher.connect(lambda: heard.append(launcher.running_game))

game = library.add('Quick', executable=str(launcher_script('quick',
                                                           'exec sleep 1')))
launcher.launch(game)
check('the running game is known', launcher.running_game == game)
check('listeners hear the start', heard == [game], heard)
check('starting moves new to playing',
      library.get(game).status == 'playing')
check('and stamps last played', library.get(game).last_played is not None)
check('a session is open while it runs', library._db.execute(
    'SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL').fetchone()[0] == 1)
check('a second game cannot start meanwhile',
      raises(AlreadyRunning, launcher.launch, game))

pump()
check('listeners hear the end', heard == [game, None], heard)
check('nothing is running afterwards', launcher.running_game is None)
check('the session is closed', library._db.execute(
    'SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL').fetchone()[0] == 0)
row = library._db.execute('SELECT * FROM sessions').fetchone()
check('the measured seconds are stored, at least a minute',
      row['seconds'] == 60, row['seconds'])
check('and added to the playtime', library.get(game).playtime == 60)

broken = library.add('Broken', executable=str(games / 'gone' / 'run.sh'))
check('a game whose launcher is gone does not start',
      raises(LaunchError, launcher.launch, broken))
check('and is left exactly as it was',
      library.get(broken).status == 'new'
      and library.get(broken).last_played is None)
check('without a session', library._db.execute(
    'SELECT COUNT(*) FROM sessions WHERE game_id = ?', (broken,)
).fetchone()[0] == 0)
check('an unknown game does not start',
      raises(LaunchError, launcher.launch, 9999))

stoppable = library.add('Stoppable', executable=str(
    launcher_script('stoppable', 'exec sleep 30')))
launcher.launch(stoppable)
time.sleep(0.3)
launcher.stop()
pump()
check('a stopped game is credited too', library.get(stoppable).playtime == 60)
check('and nothing runs afterwards', launcher.running_game is None)

section('Leftovers')

check('nothing was handed over that was not picked up', handed_over.empty())

library.close()
report(folder)
