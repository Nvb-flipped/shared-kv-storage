"""Small command dispatcher; each workflow has its own --help."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description='Local key-value storage framework for academic study.')
    parser.add_argument('command', choices=['demo', 'client', 'study', 'report', 'check'])
    args = parser.parse_args(sys.argv[1:2])
    rest = sys.argv[2:]
    sys.argv = [f'sharedkv {args.command}', *rest]
    if args.command == 'demo':
        from .cluster import main as run
    elif args.command == 'client':
        from .cli import main as run
    elif args.command == 'study':
        from .study import main as run
    else:
        from .analysis import main as run
        if args.command == 'check':
            sys.argv.append('--check-only')
    return run()


if __name__ == '__main__':
    raise SystemExit(main())
