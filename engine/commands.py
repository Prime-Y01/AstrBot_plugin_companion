# -*- coding: utf-8 -*-
"""Consume panel commands from data/ui_commands/."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime

from .store import Store
from .tick import _room_for

ALLOWED = ("sleep", "wake", "eat", "water", "out", "praise", "quiet")
TTL = 600
_LABELS = {
    "sleep": "去睡觉",
    "wake": "起床",
    "eat": "去吃饭",
    "water": "喝点水",
    "out": "出门走走",
    "praise": "夸她一句",
    "quiet": "安静一会儿",
}


def _set_activity(store, now, activity_id, label, minutes, room_id=None):
    state = store.read("rhythm/state.json", {}) or {}
    old = state.get("activity") if isinstance(state.get("activity"), dict) else {}
    history = state.get("history") if isinstance(state.get("history"), list) else []
    history = history[-48:] + [{"id": old.get("id") or "idle", "to": int(now)}]
    state["activity"] = {
        "id": activity_id,
        "label": label,
        "started": int(now),
        "expected_end": int(now + minutes * 60),
        "with_owner": False,
        "deep": activity_id in ("sleep", "nap"),
    }
    state["with_owner"] = False
    state["history"] = history
    state["updated_at"] = int(now)
    store.write("rhythm/state.json", state)

    room = _room_for(room_id or activity_id)
    now_data = store.read("now.json", {}) or {}
    now_data.update({"place": room["place"], "room": room["room"], "updated_at": int(now)})
    store.write("now.json", now_data)


def _bump_mood(store, now, amount):
    mood = store.read("mood.json", {}) or {}
    try:
        value = float(mood.get("value"))
    except (TypeError, ValueError):
        value = 0.62
    value = max(0.0, min(1.0, value + amount))
    store.write("mood.json", {"value": round(value, 4), "baseline": 0.62, "ts": int(now)})


def _apply(store, cmd, now):
    if cmd == "sleep":
        _set_activity(store, now, "sleep", "睡觉", 480)
        return "他让我去睡"
    if cmd == "wake":
        _set_activity(store, now, "idle", "发呆", 30, room_id="living")
        return "他叫我起来"
    if cmd == "eat":
        _set_activity(store, now, "eat", "吃饭", 40, room_id="eat")
        return "他让我去吃饭"
    if cmd == "out":
        _set_activity(store, now, "out", "出门", 90, room_id="out")
        return "他让我出门走走"
    if cmd == "water":
        _bump_mood(store, now, 0.02)
        return "他提醒我喝水"
    if cmd == "praise":
        _bump_mood(store, now, 0.05)
        return "他夸我了"
    if cmd == "quiet":
        _set_activity(store, now, "idle", "发呆", 15, room_id="living")
        return "他要我安静一会儿"
    raise ValueError("unknown")


def _archive(store, path, status):
    done = store.path("ui_commands/done")
    done.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except Exception:
        data = {}
    data["status"] = status
    data["handled_at"] = int(time.time())
    try:
        (done / (path.stem + ".json")).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    try:
        path.unlink()
    except OSError:
        pass


def consume(store: Store, now=None):
    now = time.time() if now is None else float(now)
    base = store.path("ui_commands")
    base.mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted(base.glob("*.json")):
        if not re.match(r"^[A-Za-z0-9._-]{1,80}$", path.stem):
            _archive(store, path, "failed")
            results.append("bad_id:failed")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            _archive(store, path, "failed")
            results.append(path.stem + ":failed")
            continue
        if not isinstance(data, dict):
            _archive(store, path, "failed")
            results.append(path.stem + ":failed")
            continue
        cmd = str(data.get("cmd") or "").strip()
        try:
            at = float(data.get("at") or 0)
        except (TypeError, ValueError):
            at = 0
        if cmd not in ALLOWED:
            _archive(store, path, "unknown")
            results.append(cmd + ":unknown")
            continue
        if not at or now - at > TTL:
            _archive(store, path, "expired")
            results.append(cmd + ":expired")
            continue
        try:
            note = _apply(store, cmd, now)
            _archive(store, path, "done")
            store.append_jsonl("timeline/%s.jsonl" % datetime.fromtimestamp(now).strftime("%Y-%m-%d"), {
                "ts": int(now),
                "kind": "ui",
                "text": note,
            })
            results.append(cmd + ":done")
        except Exception:
            _archive(store, path, "failed")
            results.append(cmd + ":failed")
    return results
