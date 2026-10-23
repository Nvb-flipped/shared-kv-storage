"""Create a report for a configurable study run; --input is required."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sharedkv.analysis import main

if __name__ == '__main__':
    raise SystemExit(main())
