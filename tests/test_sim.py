# -*- coding: utf-8 -*-
"""The portable sim must run with only the plugin and example data."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "sim" / "sim_her.py"


class SimTest(unittest.TestCase):
    def run_sim(self, *args):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, str(SIM), "--json", *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        lines = [line for line in proc.stdout.splitlines() if line.startswith("SUMMARY ")]
        self.assertTrue(lines, proc.stdout)
        return json.loads(lines[-1][8:])

    def test_full(self):
        data = self.run_sim("--scenario", "full")
        self.assertTrue(data["all_pass"])
        self.assertGreater(data["total"], 0)
        self.assertTrue(data["sha_ok"])
        self.assertTrue(data["temp_removed"])

    def test_weather_matrix(self):
        data = self.run_sim("--scenario", "weather_matrix")
        self.assertTrue(data["all_pass"])
        self.assertEqual(len(data["data"]["weather"]), 5)

    def test_outing_day(self):
        data = self.run_sim(
            "--scenario", "outing_day", "--place", "demo_park",
            "--weather", "rain", "--mood", "0.6", "--pain", "0.2",
            "--energy", "0.7", "--scene", "长椅",
        )
        self.assertTrue(data["all_pass"])
        self.assertEqual(data["data"]["outing"]["place"], "示例公园")

    def test_custom_outing(self):
        data = self.run_sim(
            "--scenario", "outing_day", "--place", "custom",
            "--place-name", "自定义商场", "--address", "自定义路9号",
            "--location", "121.4,31.2", "--route-minutes", "18",
            "--fare", "3", "--weather-text", "沙尘", "--scene", "包间",
        )
        self.assertTrue(data["all_pass"])
        self.assertEqual(data["data"]["outing"]["address"], "自定义路9号")
        self.assertEqual(data["data"]["outing"]["route_minutes"], 18.0)


if __name__ == "__main__":
    unittest.main()
