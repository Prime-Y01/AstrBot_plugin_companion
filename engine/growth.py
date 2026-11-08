# -*- coding: utf-8 -*-
"""Tiny growth adapter: add a milestone when a real chat contains 第一次."""
from __future__ import annotations

import hashlib
import sqlite3
import time

from .store import Store


def maybe_add_first(store: Store, text_value, now=None):
    text_value = (text_value or "").strip()
    if "第一次" not in text_value:
        return None
    now = time.time() if now is None else float(now)
    path = store.path("growth/growth.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    key = "chat_" + hashlib.sha1(text_value.encode("utf-8")).hexdigest()[:12]
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "create table if not exists milestones ("
            "id integer primary key autoincrement, ts integer, text text, key text, "
            "kind text, source text, created integer, status text)"
        )
        if con.execute("select 1 from milestones where key = ? limit 1", (key,)).fetchone():
            return None
        con.execute(
            "insert into milestones (ts, text, key, kind, source, created, status) "
            "values (?, ?, ?, ?, ?, ?, ?)",
            (int(now), text_value[:60], key, "first", "chat", int(now), "active"),
        )
        con.commit()
        return key
    finally:
        con.close()
