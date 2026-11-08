# -*- coding: utf-8 -*-
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from engine.commands import consume
from engine.seed import seed
from engine.store import Store
from engine.tick import tick


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="companion_"))
        self.store = seed(self.tmp, demo=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_seed(self):
        self.assertEqual(self.store.read("rhythm/state.json")["activity"]["id"] in ("sleep", "eat", "study", "nap", "draw", "out", "watch"), True)
        self.assertEqual(len(self.store.read("exports/memory_export.json")["items"]), 30)
        self.assertTrue(self.store.path("growth/growth.db").exists())
        self.assertTrue(self.store.path("emotion/shadow.jsonl").exists())

    def test_seed_idempotent(self):
        self.store.write("rhythm/state.json", {"activity": {"id": "custom"}})
        seed(self.tmp, demo=True)
        self.assertEqual(self.store.read("rhythm/state.json")["activity"]["id"], "custom")

    def test_command(self):
        before = self.store.read("mood.json")["value"]
        queue = self.store.path("ui_commands")
        (queue / "panel-test.json").write_text(
            json.dumps({"id": "panel-test", "cmd": "praise", "at": int(time.time())}),
            encoding="utf-8",
        )
        self.assertEqual(consume(self.store), ["praise:done"])
        self.assertAlmostEqual(self.store.read("mood.json")["value"], before + 0.05, places=3)
        done = json.loads(self.store.path("ui_commands/done/panel-test.json").read_text(encoding="utf-8"))
        self.assertEqual(done["status"], "done")

    def test_expired(self):
        queue = self.store.path("ui_commands")
        (queue / "panel-old.json").write_text(
            json.dumps({"id": "panel-old", "cmd": "sleep", "at": int(time.time()) - 700}),
            encoding="utf-8",
        )
        self.assertEqual(consume(self.store), ["sleep:expired"])

    def test_tick(self):
        state = self.store.read("rhythm/state.json")
        state["activity"]["expected_end"] = int(time.time()) - 1
        self.store.write("rhythm/state.json", state)
        self.assertTrue(tick(self.store, time.time()))
        self.assertNotEqual(self.store.read("rhythm/state.json")["activity"]["expected_end"], state["activity"]["expected_end"])


if __name__ == "__main__":
    unittest.main()
