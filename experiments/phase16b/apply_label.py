#!/usr/bin/env python3
"""Rerun the Phase 16b merge check against the current label file and refresh the summary."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    os.chdir(ROOT)
    os.environ["PHASE16B_WRITE"] = "1"
    subprocess.check_call(
        ["cargo", "test", "--offline", "--test", "phase16b", "--", "--nocapture"]
    )
    subprocess.check_call([sys.executable, str(ROOT / "experiments" / "phase16b" / "write_summary.py")])


if __name__ == "__main__":
    main()
