"""A storage process owns text values, without placement or record versions."""
import os
import threading
from urllib.parse import unquote
from .transport import ApiError, fields, require, text_key


class Storage:
    def __init__(self, node_id):
        self.id, self.kv = node_id, {}
        self.lock = threading.RLock()

    def handle(self, method, path, query, data):
        with self.lock:
            if path in ('/health', '/stats'):
                require(method, 'GET')
                return {'id': self.id, 'status': 'ok', 'key_count': len(self.kv), 'pid': os.getpid()}
            if path == '/keys':
                if method == 'GET':
                    return {'keys': sorted(self.kv)}
                require(method, 'DELETE')
                count = len(self.kv); self.kv.clear()
                return {'ok': True, 'deleted': count}
            if path == '/migrate_in':
                require(method, 'POST'); fields(data, ['items'])
                if not isinstance(data['items'], list):
                    raise ApiError(400, 'invalid_items', 'items must be a list.')
                staged = {}
                for item in data['items']:
                    if not isinstance(item, dict):
                        raise ApiError(400, 'invalid_items', 'Each item needs a key and text value.')
                    fields(item, ['key', 'value']); key = text_key(item['key'])
                    if not isinstance(item['value'], str) or key in staged:
                        raise ApiError(400, 'invalid_items', 'Values must be text and batch keys distinct.')
                    staged[key] = item['value']
                self.kv.update(staged)
                return {'ok': True, 'count': len(staged)}
            if not path.startswith('/kv/'):
                raise ApiError(404, 'unknown_endpoint', 'Unknown storage endpoint.')
            key = text_key(unquote(path[4:], errors='strict'))
            if method == 'PUT':
                fields(data, ['value'])
                if not isinstance(data['value'], str):
                    raise ApiError(400, 'invalid_value', 'Values must be text.')
                self.kv[key] = data['value']
                return {'ok': True}
            if method == 'GET':
                if key not in self.kv:
                    raise ApiError(404, 'not_found', 'The key does not exist.', {'key': key})
                return {'key': key, 'value': self.kv[key]}
            require(method, 'DELETE')
            self.kv.pop(key, None)
            return {'ok': True}


def main():
    import argparse
    from .transport import serve
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', required=True)
    parser.add_argument('--port', required=True, type=int)
    args = parser.parse_args()
    if len(args.id) != 1 or not 'A' <= args.id <= 'Z':
        parser.error('--id must be one uppercase letter A–Z')
    if not 1 <= args.port <= 65535:
        parser.error('--port must be an integer from 1 to 65535')
    try:
        serve(Storage(args.id), args.port)
    except OSError as exc:
        parser.exit(1, f'Cannot start storage on port {args.port}: {exc}\n')


if __name__ == '__main__':
    main()
