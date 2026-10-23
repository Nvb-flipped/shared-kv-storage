"""Bounded JSON transport shared by independent applications."""
import json
import math
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

MAX_BODY = 1024 * 1024


def decode_json(raw):
    """Reject ambiguous objects and non-finite numbers at JSON boundaries."""
    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('JSON numbers must be finite.')
        return number

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('JSON object contains a repeated field.')
            result[key] = value
        return result

    return json.loads(raw, parse_float=finite, parse_constant=finite, object_pairs_hook=pairs)


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
            result = decode_json(response.read())
            if not isinstance(result, dict):
                raise ValueError('Expected a JSON object.')
            return result
    except HTTPError as exc:
        try:
            result = decode_json(exc.read())
            if not isinstance(result, dict) or not isinstance(result.get('error'), str) or not isinstance(result.get('message'), str) or not isinstance(result.get('details', {}), dict):
                raise ValueError('Invalid error envelope.')
            raise ApiError(exc.code, result['error'], result['message'], result.get('details')) from exc
        except (ValueError, KeyError, TypeError, RecursionError, HTTPException):
            raise ApiError(exc.code, 'invalid_response', 'The server returned an invalid error response.') from exc
        finally:
            exc.close()
    except (URLError, TimeoutError, ConnectionError, OSError, HTTPException) as exc:
        raise ApiError(503, 'node_unavailable', 'The destination is unreachable or timed out.') from exc
    except (ValueError, UnicodeError, RecursionError) as exc:
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
    timeout = 10

    def setup(self):
        super().setup()
        self.connection.settimeout(self.timeout)

    def log_message(self, *args):
        pass

    def dispatch(self):
        try:
            if self.headers.get('Transfer-Encoding'):
                raise ApiError(400, 'invalid_request', 'Use Content-Length, not chunked requests.')
            lengths = self.headers.get_all('Content-Length', ['0'])
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal():
                raise ValueError('invalid or repeated length')
            length = int(lengths[0])
            if length > MAX_BODY:
                self.close_connection = True
                raise ApiError(413, 'body_too_large', 'The body limit is 1 MiB.')
            if length and self.headers.get_content_type() != 'application/json':
                raise ApiError(415, 'unsupported_media_type', 'Use Content-Type: application/json.')
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('incomplete body')
            data = decode_json(raw) if raw else {}
            if not isinstance(data, dict):
                raise ValueError('body is not an object')
            json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            url = urlsplit(self.path)
            query = parse_qs(url.query, keep_blank_values=True, encoding='utf-8', errors='strict')
            result = self.server.app.handle(self.command, url.path, query, data)
            status = 200
        except ApiError as exc:
            status, result = exc.status, exc.json()
        except TimeoutError:
            self.close_connection = True
            status, result = 408, ApiError(408, 'request_timeout', 'The request body timed out.').json()
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            status, result = 400, ApiError(400, 'invalid_request', 'Invalid JSON, header or request field.').json()
        except Exception as exc:
            print(json.dumps({'internal_error': repr(exc)}), flush=True)
            status, result = 500, ApiError(500, 'internal_error', 'Internal server error.').json()
        try:
            body = json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (ValueError, TypeError, RecursionError, UnicodeError):
            status = 500
            body = json.dumps(ApiError(500, 'internal_error', 'Invalid application response.').json()).encode('utf-8')
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        except OSError:
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
