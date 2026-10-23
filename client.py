"""Compatibility entry point; implementation lives in the sharedkv package."""
from sharedkv.cli import HELP, command, execute, main

if __name__ == '__main__':
    raise SystemExit(main())
