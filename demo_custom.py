#!/usr/bin/env python3
"""One-command custom-outing demo (example data + temp directory only)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CMD = [
    sys.executable, str(ROOT / "sim" / "sim_her.py"),
    "--scenario", "outing_day",
    "--place", "custom",
    "--place-name", "自定义商场",
    "--address", "自定义路9号",
    "--district", "示例区",
    "--station", "自定义站",
    "--line", "9号线",
    "--location", "121.400000,31.200000",
    "--route-minutes", "18",
    "--fare", "3",
    "--weather-text", "沙尘",
    "--scene", "包间",
    "--mood", "0.6",
    "--pain", "0.2",
    "--energy", "0.7",
    "--seed", "7",
    "--json",
]


def main() -> int:
    proc = subprocess.run(CMD, cwd=str(ROOT))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
