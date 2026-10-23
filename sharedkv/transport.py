"""Bounded JSON transport shared by independent applications."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

MAX_BODY = 1024 * 1024


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status, self.code, self.details = status, code, details or {}

    def json(self):
        return {'error': self.code, 'message': str(self), 'details': self.details}


def request(base, route, method='GET', data=None, timeout=30):
    raw = None if data is None else json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
    req = Request(base.rstrip('/')+route, raw, {'Content-Type': 'application/json'}, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            result = json.loads(exc.read())
            raise ApiError(exc.code, result['error'], result['message'], result.get('details')) from exc
        except (ValueError, KeyError, TypeError):
            raise ApiError(exc.code, 'invalid_response', 'The server returned an invalid error response.') from exc
        finally:
            exc.close()
    except (URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise ApiError(503, 'node_unavailable', 'The destination is unreachable or timed out.') from exc
    except (ValueError, UnicodeError) as exc:
        raise ApiError(502, 'invalid_response', 'The server returned invalid JSON.') from exc


def require(method, expected):
    if method != expected:
        raise ApiError(405, 'method_not_allowed', f'Use {expected} for this endpoint.')


def text_key(key):
    if not isinstance(key, str) or not 1 <= len(key.encode('utf-8')) <= 1024:
        raise ApiError(400, 'invalid_key', 'A key must contain 1–1024 UTF-8 bytes.')
    return key


def fields(data, names):
    if set(data) != set(names):
        raise ApiError(400, 'invalid_fields', 'Required fields: '+', '.join(names)+'.')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def dispatch(self):
        try:
            if self.headers.get('Transfer-Encoding'):
                raise ApiError(400, 'invalid_request', 'Use Content-Length, not chunked requests.')
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0:
                raise ValueError('negative length')
            if length > MAX_BODY:
                self.close_connection = True
                raise ApiError(413, 'body_too_large', 'The body limit is 1 MiB.')
            if length and self.headers.get_content_type() != 'application/json':
                raise ApiError(415, 'unsupported_media_type', 'Use Content-Type: application/json.')
            raw = self.rfile.read(length)
            def invalid_constant(value):
                raise ValueError(value)
            data = json.loads(raw, parse_constant=invalid_constant) if raw else {}
            if not isinstance(data, dict):
                raise ValueError('body is not an object')
            json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            url = urlsplit(self.path)
            query = parse_qs(url.query, keep_blank_values=True, encoding='utf-8', errors='strict')
            result = self.server.app.handle(self.command, url.path, query, data)
            status = 200
        except ApiError as exc:
            status, result = exc.status, exc.json()
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            status, result = 400, ApiError(400, 'invalid_request', 'Invalid JSON, header or request field.').json()
        except Exception as exc:
            print(json.dumps({'internal_error': repr(exc)}), flush=True)
            status, result = 500, ApiError(500, 'internal_error', 'Internal server error.').json()
        body = json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = dispatch


def server(app, port):
    http = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    http.daemon_threads = True
    http.app = app
    return http


def serve(app, port):
    with server(app, port) as http:
        try:
            http.serve_forever()
        except KeyboardInterrupt:
            pass
