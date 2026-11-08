# -*- coding: utf-8 -*-
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from engine.seed import seed

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_port(port, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.1)
    return False


class PanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="companion_panel_"))
        seed(cls.tmp, demo=True)
        cls.port = free_port()
        cls.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "panel" / "server.py"), "--data-dir", str(cls.tmp), "--port", str(cls.port)],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_port(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except Exception:
            cls.proc.kill()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def post(self, path, payload):
        req = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Panel": "1",
                "Origin": "http://127.0.0.1:%d" % self.port,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_payload(self):
        status, data = self.get("/api/all")
        self.assertEqual(status, 200)
        self.assertEqual(data["profile"]["her_name"], "她")
        self.assertTrue(data["features"]["sim"])
        self.assertTrue(data["features"]["commands"])
        self.assertFalse(data["features"]["memory_edit"])

    def test_command_queue(self):
        status, data = self.post("/api/cmd", {"cmd": "praise"})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        files = list((self.tmp / "ui_commands").glob("panel-*.json"))
        self.assertEqual(len(files), 1)

    def test_disabled_features(self):
        status, _ = self.post("/api/memory/command", {"op": "pin", "target": 1})
        self.assertEqual(status, 403)
        status, data = self.get("/api/sim/status")
        self.assertEqual(status, 200)
        self.assertIn("status", data)


class ExternalPanelTest(unittest.TestCase):
    """A mode: read external state, write cache/log only to runtime."""

    @classmethod
    def setUpClass(cls):
        cls.state = Path(tempfile.mkdtemp(prefix="companion_state_"))
        cls.runtime = Path(tempfile.mkdtemp(prefix="companion_runtime_"))
        seed(cls.state, demo=True)
        shutil.rmtree(cls.state / "panel_cache", ignore_errors=True)
        shutil.rmtree(cls.state / "panel_logs", ignore_errors=True)
        try:
            (cls.state / "panel_profile.json").unlink()
        except OSError:
            pass
        (cls.runtime / "panel_profile.json").write_text(
            json.dumps({
                "profile": {"her_name": "外部她"},
                "features": {"memory": True, "memory_edit": False, "sim": False, "commands": True},
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        cls.port = free_port()
        cls.proc = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "panel" / "server.py"),
                "--data-dir", str(cls.state),
                "--runtime-dir", str(cls.runtime),
                "--profile", str(cls.runtime / "panel_profile.json"),
                "--port", str(cls.port),
            ],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_port(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except Exception:
            cls.proc.kill()
        shutil.rmtree(cls.state, ignore_errors=True)
        shutil.rmtree(cls.runtime, ignore_errors=True)

    def test_external_profile_and_runtime(self):
        with urllib.request.urlopen("http://127.0.0.1:%d/api/all" % self.port, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data["profile"]["her_name"], "外部她")
        self.assertTrue((self.runtime / "panel_logs" / "panel.log").exists())
        self.assertFalse((self.state / "panel_cache").exists())
        self.assertFalse((self.state / "panel_logs").exists())


if __name__ == "__main__":
    unittest.main()
