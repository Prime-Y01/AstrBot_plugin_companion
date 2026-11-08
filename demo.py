# -*- coding: utf-8 -*-
"""Seed demo data and run the panel without AstrBot."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from engine.seed import seed

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "demo_data"


def main():
    seed(DATA, demo=True)
    print("demo data:", DATA)
    return subprocess.call([
        sys.executable,
        str(ROOT / "panel" / "server.py"),
        "--data-dir",
        str(DATA),
        "--port",
        "8780",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
