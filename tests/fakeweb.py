'''A small web server on 127.0.0.1 with images and things that are not,
for the tests that load from links. Nothing leaves this machine.

    from fakeweb import BASE, PNG, JPEG
'''

import http.server
import threading
import time

import gi

gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf  # noqa: E402


def encoded(kind):
    '''A small real image as bytes, in `kind` ('png' or 'jpeg').'''
    pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 32, 18)
    pixbuf.fill(0x3366ccff)
    ok, data = pixbuf.save_to_bufferv(kind, [], [])
    return data


PNG = encoded('png')
JPEG = encoded('jpeg')
SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
       b'<rect width="10" height="10"/></svg>')

# path -> (status, content type, body, extra headers)
ROUTES = {
    '/cover.png': (200, 'image/png', PNG, {}),
    '/photo.jpg': (200, 'image/jpeg', JPEG, {}),
    '/itch/cover.png': (200, 'image/jpeg; charset=binary', JPEG, {}),
    '/mislabelled': (200, 'image/jpeg', PNG, {}),
    '/page': (200, 'text/html; charset=utf-8', b'<html></html>', {}),
    '/liar.png': (200, 'image/png', b'this is not a picture', {}),
    '/drawing.svg': (200, 'image/svg+xml', SVG, {}),
    '/svg-as-png': (200, 'image/png', SVG, {}),
    '/notype': (200, '', PNG, {}),
    '/big': (200, 'image/png', PNG + b'\0' * 4000, {}),
    '/redirect': (302, 'text/plain', b'', {'Location': '/cover.png'}),
    '/to-ftp': (302, 'text/plain', b'',
                {'Location': 'ftp://127.0.0.1/cover.png'}),
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/slow':
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.end_headers()
            for byte in PNG[:40]:
                self.wfile.write(bytes([byte]))
                self.wfile.flush()
                time.sleep(0.1)
            return
        if path == '/cut-short':
            # Promises more than it sends, then hangs up.
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(PNG) * 2))
            self.end_headers()
            self.wfile.write(PNG)
            self.close_connection = True
            return
        if path == '/big-unannounced':
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.end_headers()  # no Content-Length
            self.wfile.write(PNG + b'\0' * 4000)
            return
        status, kind, body, extra = ROUTES.get(
            path, (404, 'text/plain', b'nope', {}))
        self.send_response(status)
        if kind:
            self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        for key, value in extra.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class Server(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # a client that gave up on purpose (too slow, too big)


server = Server(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{server.server_address[1]}'
