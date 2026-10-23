"""Start the standalone coordinator; only this application computes owners."""
import argparse
from sharedkv.router import Router
from sharedkv.transport import serve

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--nodes', default='A=localhost:5001,B=localhost:5002,C=localhost:5003')
    parser.add_argument('--placement', choices=['modulo', 'consistent'], default='consistent')
    parser.add_argument('--vnodes', type=int, default=16)
    args = parser.parse_args()
    try:
        pairs = [item.split('=', 1) for item in args.nodes.split(',')]
        nodes = dict(pairs)
        if len(nodes) != len(pairs) or any(len(n) != 1 or not 'A' <= n <= 'Z' for n in nodes):
            raise ValueError('Use distinct uppercase node IDs, for example A=localhost:5001.')
        app = Router(nodes, args.placement, args.vnodes)
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))
    serve(app, args.port)
