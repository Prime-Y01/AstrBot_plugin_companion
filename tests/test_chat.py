# -*- coding: utf-8 -*-
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from engine.chat import on_message
from engine.memory import load_export
from engine.seed import seed


class ChatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="companion_chat_"))
        self.store = seed(self.tmp, demo=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_owner_message(self):
        before = self.store.read("mood.json")["value"]
        result = on_message(self.store, "今天第一次和你一起看海，我很开心", now=time.time())
        self.assertTrue(result["positive"])
        self.assertGreater(self.store.read("mood.json")["value"], before)
        self.assertEqual(self.store.read("rhythm/state.json")["activity"]["id"], "chat_together")
        self.assertIn("和你说了一会儿话", self.store.read("her_life.json")["events"])
        self.assertEqual(len(load_export(self.store)["items"]), 31)
        self.assertTrue(result["growth"])
        con = sqlite3.connect(str(self.store.path("growth/growth.db")))
        try:
            count = con.execute("select count(*) from milestones where source='chat'").fetchone()[0]
        finally:
            con.close()
        self.assertEqual(count, 1)

    def test_throttle(self):
        now = time.time()
        on_message(self.store, "第一句话在这里", now=now)
        on_message(self.store, "第二句话在这里", now=now + 10)
        self.assertEqual(len(load_export(self.store)["items"]), 31)

    def test_not_owner(self):
        before = len(load_export(self.store)["items"])
        on_message(self.store, "群友说的话", is_owner=False, now=time.time())
        self.assertEqual(len(load_export(self.store)["items"]), before)


if __name__ == "__main__":
    unittest.main()
