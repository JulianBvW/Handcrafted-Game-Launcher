'''Images from links, against a server of our own on 127.0.0.1.

    /usr/bin/python3 tests/test_download.py

Nothing leaves this machine. Takes a few seconds: one case waits for a
deliberately slow answer.
'''

import queue
import tempfile
import time
from pathlib import Path

from fakeweb import BASE, JPEG, PNG
from harness import check, report, sandbox, section

from handcrafted import download  # noqa: E402
from handcrafted.download import DownloadError, Loader  # noqa: E402

folder = sandbox()


target = Path(tempfile.mkdtemp(dir=folder))


def fails(url, expected):
    try:
        download.fetch(url, target)
    except DownloadError as error:
        return expected in str(error), str(error)
    return False, 'loaded'


section('Reading the field')

links, rejected, later = download.parse(
    'https://a.example/1.png\n\n   \nnot a link\nfile:///etc/passwd\n'
    'HTTP://b.example/2.jpg\nftp://c.example/3.png\n')
check('http and https, in any case, are links',
      links == ['https://a.example/1.png', 'HTTP://b.example/2.jpg'], links)
check('everything else is refused with a reason, not dropped',
      [line for line, _ in rejected]
      == ['not a link', 'file:///etc/passwd', 'ftp://c.example/3.png'],
      rejected)
check('blank lines are simply skipped', len(links) + len(rejected) == 5)

many = '\n'.join(f'https://x.example/{n}.png' for n in range(51))
links, rejected, later = download.parse(many)
check('at most 50 at a time', len(links) == 50)
check('the 51st waits for the next Load',
      later == ['https://x.example/50.png'], later)

section('Loading one')

path = download.fetch(f'{BASE}/cover.png', target)
check('a PNG is loaded', path.read_bytes() == PNG)
check('as .png', path.suffix == '.png', path.name)
check('not executable', path.stat().st_mode & 0o111 == 0,
      oct(path.stat().st_mode))

path = download.fetch(f'{BASE}/itch/cover.png?v=3', target)
check('the extension comes from the content type, not the URL',
      path.suffix == '.jpg', path.name)

path = download.fetch(f'{BASE}/redirect', target)
check('a redirect to http is followed', path.read_bytes() == PNG)

section('Refusing')

for url, reason, name in (
        (f'{BASE}/page', 'not an image (text/html)', 'a web page'),
        (f'{BASE}/notype', 'not an image', 'no content type at all'),
        (f'{BASE}/drawing.svg', 'unsupported image type (image/svg+xml)',
         'an SVG'),
        (f'{BASE}/liar.png', 'could not be read as an image',
         'text that claims to be a PNG'),
        (f'{BASE}/svg-as-png', 'could not be read as an image',
         'an SVG that claims to be a PNG'),
        (f'{BASE}/missing.png', 'HTTP 404', 'a 404'),
        (f'{BASE}/cut-short', 'broken response', 'a response cut short'),
        (f'{BASE}/to-ftp', 'not an http(s) link', 'a redirect to ftp'),
        ('file:///etc/hostname', 'not an http(s) link', 'a file:// link'),
        ('http://127.0.0.1:1/x.png', 'refused', 'nobody listening')):
    ok, said = fails(url, reason)
    check(f'{name} is refused: {reason}', ok, said)

download.MAX_BYTES = 1024
ok, said = fails(f'{BASE}/big', 'larger than 20 MB')
check('too large, by its Content-Length', ok, said)
ok, said = fails(f'{BASE}/big-unannounced', 'larger than 20 MB')
check('too large, counted while it arrives', ok, said)
download.MAX_BYTES = 20 * 1024 * 1024

download.TIMEOUT = 1
began = time.monotonic()
ok, said = fails(f'{BASE}/slow', 'timed out')
check('too slow', ok, said)
check('and given up on in time', time.monotonic() - began < 2.5,
      f'{time.monotonic() - began:.1f} s')
download.TIMEOUT = 30

download.MAX_PIXELS = 100
ok, said = fails(f'{BASE}/cover.png', 'too large (32 × 18)')
check('an image with too many pixels is refused before decoding', ok, said)
download.MAX_PIXELS = 64_000_000

leftovers = sorted(p.name for p in target.iterdir()
                   if p.suffix not in ('.png', '.jpg'))
check('nothing half-loaded is left behind', leftovers == [], leftovers)

section('The loader')

handed_over = queue.Queue()
loader = Loader(lambda function, *args: handed_over.put((function, args)))
progress, results = [], []
batch = Path(tempfile.mkdtemp(dir=folder))
arrived = []
loader.start([f'{BASE}/cover.png', f'{BASE}/missing.png',
              f'{BASE}/photo.jpg'], batch,
             lambda n, total: progress.append((n, total)),
             lambda url, path: arrived.append((url, path)),
             lambda failed: results.append(failed))
check('running while it loads', loader.running)
while not results:
    function, args = handed_over.get(timeout=10)
    function(*args)
check('progress in order', progress == [(1, 3), (2, 3), (3, 3)], progress)
failed = results[0]
check('the good ones arrive one by one, in order',
      [url.rsplit('/', 1)[1] for url, _ in arrived]
      == ['cover.png', 'photo.jpg'], arrived)
check('the bad one is reported with its reason',
      failed == [(f'{BASE}/missing.png', 'HTTP 404')], failed)
check('not running afterwards', not loader.running)

progress, results = [], []
loader.start([f'{BASE}/cover.png'] * 3, batch,
             lambda n, total: progress.append(n),
             lambda url, path: results.append(url),
             lambda failed: results.append(1))
loader.cancel()
time.sleep(0.5)
while not handed_over.empty():
    function, args = handed_over.get()
    function(*args)
check('once cancelled, nothing more arrives',
      progress == [] and results == [], (progress, results))

section('The download folder')

one = download.new_folder()
check('a folder per dialog, under the cache',
      one.parent == folder / 'cache' / 'downloads', one)
check('private to this user', one.stat().st_mode & 0o077 == 0)
download.remove_folder(one)
check('removed when done', not one.exists())
download.new_folder()
download.clear_all()
check('clear_all leaves nothing',
      not (folder / 'cache' / 'downloads').exists())

report(folder)
