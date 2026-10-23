"""Compatibility entry point; implementation lives in the sharedkv package."""
from sharedkv.experiment import dataset, run_case, verify, main

if __name__ == '__main__':
    raise SystemExit(main())
