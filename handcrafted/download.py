'''Images from a list of links.

The one place Handcrafted goes on the network, and only for the addresses
pasted into the dialog, only when Load is pressed. What comes back is not
trusted: it has to say it is an image, be one of a few known kinds, stay
under a size and a time limit, and then actually open as an image. It is
only ever read as one -- never executed, never kept if it fails.

The file's extension comes from the response's Content-Type, never from the
URL: a link ending in .png?v=3 may well serve a JPEG.

No GTK interface here, so it can be tested without a display. GdkPixbuf is
used for the one thing it is for: telling whether a file is an image.
'''

import http.client
import os
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import gi

gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf, GLib  # noqa: E402

from . import __version__, config  # noqa: E402
from .i18n import _  # noqa: E402

MAX_BYTES = 20 * 1024 * 1024
TIMEOUT = 30           # seconds, per image, from asking to the last byte
MAX_LINKS = 50         # per press of Load
CHUNK = 64 * 1024

# What is accepted, and the extension it is stored under. All of these are
# photographs or drawings GdkPixbuf reads on this machine. SVG is not among
# them: it is a document that can carry scripts, not a picture.
TYPES = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',     # not a registered type, but servers send it
    'image/png': '.png',
    'image/webp': '.webp',
    'image/gif': '.gif',
    'image/avif': '.avif',
}

# The same kinds, as GdkPixbuf names what it finds inside the file. Checked
# too, so a server that calls an SVG image/png does not get it through.
# The AVIF loader is called 'heif/avif' here and 'avif' by libavif's own.
FORMATS = {'jpeg', 'png', 'webp', 'gif', 'heif/avif', 'avif'}

# 20 MB of compressed file can still claim to be 40000 x 40000 pixels and
# want 6 GB once decoded. Checked before decoding; 64 megapixels is several
# times any screenshot or key art.
MAX_PIXELS = 64_000_000

USER_AGENT = (f'Handcrafted/{__version__} '
              '(+https://github.com/JulianBvW/Handcrafted-Game-Launcher)')


class DownloadError(Exception):
    '''An image could not be loaded. str() is the reason, as shown.'''


def is_link(line):
    return urllib.parse.urlsplit(line).scheme.lower() in ('http', 'https')


def parse(text):
    '''Split the link field into what to load now, what is refused, and
    what waits for the next Load.

    Returns (links, rejected, later): links to load, at most MAX_LINKS;
    [(line, reason)] for lines that are not http(s) links -- shown rather
    than dropped, so a typo does not silently vanish; and the links beyond
    the limit, which stay in the field.
    '''
    links, rejected = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if is_link(line):
            links.append(line)
        else:
            rejected.append((line, _('not an http(s) link')))
    return links[:MAX_LINKS], rejected, links[MAX_LINKS:]


class _HttpOnlyRedirects(urllib.request.HTTPRedirectHandler):
    '''Follow redirects, but only to http and https. urllib on its own
    would follow one to ftp:// as well.'''

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_link(newurl):
            raise DownloadError(_('not an http(s) link'))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_HttpOnlyRedirects)


def fetch(url, folder, cancelled=None):
    '''Load one image into `folder` and return its path.

    Raises DownloadError with the reason if anything about it is wrong;
    nothing is left behind then. `cancelled` is a threading.Event that
    stops it between two blocks.
    '''
    if not is_link(url):
        raise DownloadError(_('not an http(s) link'))

    deadline = time.monotonic() + TIMEOUT
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    part = folder / f'{uuid.uuid4().hex}.part'
    try:
        with _opener.open(request, timeout=TIMEOUT) as response:
            kind = (response.headers.get('Content-Type') or '')
            kind = kind.split(';')[0].strip().lower()
            if not kind.startswith('image/'):
                raise DownloadError(_('not an image ({type})').format(
                    type=kind or _('no type given')))
            if kind not in TYPES:
                raise DownloadError(
                    _('unsupported image type ({type})').format(type=kind))

            length = response.headers.get('Content-Length')
            if length and length.isdigit() and int(length) > MAX_BYTES:
                raise DownloadError(_('larger than 20 MB'))

            received = 0
            with open(part, 'wb') as out:
                os.chmod(part, 0o644)  # an image, never anything to run
                while True:
                    if cancelled is not None and cancelled.is_set():
                        raise DownloadError(_('cancelled'))
                    if time.monotonic() > deadline:
                        raise DownloadError(_('timed out'))
                    # read1, not read: read(CHUNK) waits until a whole
                    # block is together, and a server dripping one byte at a
                    # time would never let the deadline be looked at.
                    block = response.read1(CHUNK)
                    if not block:
                        break
                    received += len(block)
                    # Counted as it arrives: Content-Length may be missing
                    # or lie.
                    if received > MAX_BYTES:
                        raise DownloadError(_('larger than 20 MB'))
                    out.write(block)
            if length and length.isdigit() and received < int(length):
                # The connection ended before what was announced arrived.
                raise DownloadError(_('broken response'))

        _check_image(part)
        final = part.with_suffix(TYPES[kind])
        part.rename(final)
        return final

    except DownloadError:
        part.unlink(missing_ok=True)
        raise
    except urllib.error.HTTPError as error:
        part.unlink(missing_ok=True)
        raise DownloadError(f'HTTP {error.code}') from error
    except urllib.error.URLError as error:
        part.unlink(missing_ok=True)
        reason = error.reason
        if isinstance(reason, TimeoutError):
            raise DownloadError(_('timed out')) from error
        raise DownloadError(getattr(reason, 'strerror', None)
                            or str(reason)) from error
    except TimeoutError as error:
        part.unlink(missing_ok=True)
        raise DownloadError(_('timed out')) from error
    except http.client.HTTPException as error:
        # A response cut short, a garbled status line, ...
        part.unlink(missing_ok=True)
        raise DownloadError(_('broken response')) from error
    except (OSError, ValueError) as error:
        part.unlink(missing_ok=True)
        raise DownloadError(getattr(error, 'strerror', None)
                            or str(error)) from error


def _check_image(path):
    '''Open it as an image, fully, or refuse it.'''
    try:
        info, width, height = GdkPixbuf.Pixbuf.get_file_info(str(path))
        if info is None or info.get_name() not in FORMATS:
            raise DownloadError(_('could not be read as an image'))
        if width * height > MAX_PIXELS:
            raise DownloadError(_('too large ({width} × {height})').format(
                width=width, height=height))
        GdkPixbuf.Pixbuf.new_from_file(str(path))
    except GLib.Error as error:
        raise DownloadError(_('could not be read as an image')) from error


# -- the download folder ----------------------------------------------------

def _root():
    return config.CACHE_DIR / 'downloads'


def new_folder():
    '''A folder of its own for one open dialog. Private to this user.'''
    _root().mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix='dialog-', dir=_root()))


def remove_folder(folder):
    if folder is not None:
        shutil.rmtree(folder, ignore_errors=True)


def clear_all():
    '''Everything a run left behind: called at start and at the end.'''
    shutil.rmtree(_root(), ignore_errors=True)


# -- loading in the background ----------------------------------------------

class Loader:
    '''Loads a list of links one after the other in a thread of its own.

    Everything it reports comes back through `deliver` -- GLib.idle_add in
    the application -- so the callbacks run in the main thread. Once
    cancelled, nothing more is delivered.
    '''

    def __init__(self, deliver):
        self._deliver = deliver
        self._cancelled = None

    @property
    def running(self):
        return self._cancelled is not None and not self._cancelled.is_set()

    def start(self, links, folder, on_progress, on_loaded, on_done):
        '''on_progress(n, total) before each link, on_loaded(url, path) for
        each image as soon as it is there, and on_done(failed) at the end,
        with [(url, reason)]. Images arrive one by one so that whatever is
        in when the dialog is saved is not lost with the rest.'''
        self.cancel()
        cancelled = threading.Event()
        self._cancelled = cancelled
        threading.Thread(
            target=self._work,
            args=(list(links), folder, cancelled, on_progress, on_loaded,
                  on_done),
            daemon=True).start()

    def cancel(self):
        if self._cancelled is not None:
            self._cancelled.set()

    def _work(self, links, folder, cancelled, on_progress, on_loaded,
              on_done):
        '''In the loading thread.'''
        failed = []
        for n, url in enumerate(links, start=1):
            if cancelled.is_set():
                return
            self._deliver(self._relay, cancelled, on_progress, n, len(links))
            try:
                path = fetch(url, folder, cancelled)
            except DownloadError as error:
                failed.append((url, str(error)))
            except Exception as error:  # noqa: BLE001
                # Whatever it was, it is this link's failure, not the end of
                # the thread: a dead thread would leave Load stuck on
                # "Loading…" for good.
                failed.append((url, str(error) or type(error).__name__))
            else:
                self._deliver(self._relay, cancelled, on_loaded, url, path)
        self._deliver(self._relay, cancelled, self._finish, cancelled,
                      on_done, failed)

    def _relay(self, cancelled, callback, *args):
        '''Back in the main thread.'''
        if not cancelled.is_set():
            callback(*args)
        return False  # GLib.idle_add: once

    def _finish(self, cancelled, on_done, failed):
        cancelled.set()  # done: no longer running
        on_done(failed)
