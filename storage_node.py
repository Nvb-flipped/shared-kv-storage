"""Start one standalone text storage process."""
import argparse
from sharedkv.storage import Storage
from sharedkv.transport import serve

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', required=True)
    parser.add_argument('--port', required=True, type=int)
    args = parser.parse_args()
    if len(args.id) != 1 or not 'A' <= args.id <= 'Z':
        parser.error('--id must be one uppercase letter A–Z')
    serve(Storage(args.id), args.port)
