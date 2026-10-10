'''Starting a game and measuring how long it ran.

Ren'Py's launcher ends with `exec`, which replaces the shell with the game
under the same process id. So the process we start *is* the game, and
waiting for it is the whole measurement -- no process names, no polling of
/proc. `proc.wait()` sleeps in waitpid() until the kernel reports the end.

The clock is time.monotonic(), CLOCK_MONOTONIC, which stands still during
suspend: sleep is not playtime. Pauses inside the game are, since nothing
of what happens in there can be seen from outside.

Free of GTK. The thread that waits hands its result back through
`deliver`, which is GLib.idle_add in the application and a queue in the
tests, so the library is only ever touched from the main thread.
'''

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .i18n import _

# How often to look whether a launcher's leftovers are still running.
GROUP_POLL_SECONDS = 0.5


class LaunchError(Exception):
    '''The game could not be started. str() says why.'''


class AlreadyRunning(LaunchError):
    '''Another game is running. It is never stopped to make room.'''


@dataclass(frozen=True)
class Result:
    seconds: float   # monotonic, so without any time spent suspended
    exit_code: int   # negative if a signal ended it: -15 is SIGTERM
    stopped: bool    # ended by stop() rather than by itself


def check(executable):
    '''None if the launcher can be started, otherwise the reason.

    Called when a game is selected, not at program start, so games nobody
    looks at cost nothing.
    '''
    if not executable:
        return 'missing'
    path = Path(executable)
    # Relative to what? The program's working directory is an accident, and
    # a bare `run.sh` would even be looked up in $PATH.
    if not path.is_absolute() or not path.is_file():
        return 'missing'
    if not os.access(path, os.X_OK):
        return 'not executable'
    return None


def _group_alive(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Not ours to signal, so not our game: its group id has been handed
        # to someone else since. Waiting on it would never end.
        return False
    return True


class Runner:
    '''One running process and its clock. Knows nothing of the library.'''

    def __init__(self, deliver):
        self._deliver = deliver
        self._proc = None
        self._stopped = False

    @property
    def running(self):
        return self._proc is not None

    def start(self, executable, on_end):
        '''Start the launcher and call on_end(Result) in the main thread
        once it and everything it left behind has ended.'''
        if self.running:
            raise AlreadyRunning(_('another game is running'))
        problem = check(executable)
        if problem:
            raise LaunchError(problem)

        path = Path(executable)
        clock = time.monotonic()
        try:
            # A session of its own: the game gets its own process group,
            # which is what lets us wait for, and stop, everything it starts.
            proc = subprocess.Popen(
                [str(path)], cwd=path.parent, start_new_session=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
        except OSError as error:
            # A script without a shebang, a folder without permission, ...
            raise LaunchError(error.strerror or str(error)) from error

        self._proc = proc
        self._stopped = False
        threading.Thread(target=self._watch, args=(proc, clock, on_end),
                         daemon=True).start()

    def _watch(self, proc, clock, on_end):
        '''In the waiting thread.'''
        exit_code = proc.wait()
        # A launcher may send the game into the background and end at once.
        # Its process group outlives it, so that is what we wait for.
        while _group_alive(proc.pid):
            time.sleep(GROUP_POLL_SECONDS)
        result = Result(time.monotonic() - clock, exit_code, self._stopped)
        self._deliver(self._finish, on_end, result)

    def _finish(self, on_end, result):
        '''Back in the main thread.'''
        self._proc = None
        on_end(result)
        return False  # GLib.idle_add: once, not again and again

    def stop(self):
        '''Ask the game to end: SIGTERM to its whole process group.

        Nothing harder. Pulling the plug on a visual novel risks its saves,
        so a game that ignores SIGTERM simply keeps running.
        '''
        if self._proc is None:
            return
        self._stopped = True
        try:
            os.killpg(self._proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass  # already on its way out


class Launcher:
    '''Runner and library together: what the interface talks to.

    One game at a time. Its session is written only once the process is
    actually running, so a failed start leaves no session, no last_played,
    and a `new` game still new.
    '''

    def __init__(self, library, deliver):
        self._library = library
        self._runner = Runner(deliver)
        self._game_id = None
        self._session_id = None
        self._listeners = []

    @property
    def running_game(self):
        '''The id of the game that is running, or None.'''
        return self._game_id

    def connect(self, callback):
        '''callback() after every start and every end.'''
        self._listeners.append(callback)

    def launch(self, game_id):
        if self._runner.running:
            raise AlreadyRunning(_('another game is running'))
        game = self._library.get(game_id)
        if game is None:
            raise LaunchError(_('no such game'))
        self._runner.start(game.executable, self._on_end)
        self._game_id = game_id
        self._session_id = self._library.start_session(game_id)
        self._notify()

    def stop(self):
        self._runner.stop()

    def _on_end(self, result):
        session_id = self._session_id
        # Cleared first: whatever happens to the database, the game has
        # ended, and the interface must not keep showing it as running.
        self._game_id = self._session_id = None
        try:
            self._library.end_session(session_id, result.seconds,
                                      result.exit_code)
        finally:
            self._notify()

    def _notify(self):
        for callback in self._listeners:
            callback()
