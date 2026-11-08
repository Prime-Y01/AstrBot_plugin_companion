# -*- coding: utf-8 -*-
"""Time-based state transitions for the portable engine."""
from __future__ import annotations

import time
from datetime import datetime

from .store import Store


def _hours(now):
    return datetime.fromtimestamp(now).hour


def _next_activity(now):
    hour = _hours(now)
    if hour < 7:
        return "sleep", "睡觉", 3 * 3600
    if hour < 9:
        return "eat", "吃饭", 40 * 60
    if hour < 12:
        return "study", "看书", 45 * 60
    if hour < 13:
        return "eat", "吃饭", 40 * 60
    if hour < 15:
        return "nap", "午睡", 40 * 60
    if hour < 18:
        return "draw", "画画", 50 * 60
    if hour < 19:
        return "out", "出门", 30 * 60
    if hour < 21:
        return "eat", "吃饭", 40 * 60
    if hour < 23:
        return "watch", "看番", 60 * 60
    return "sleep", "睡觉", 7 * 3600


def _room_for(activity_id):
    if activity_id in ("sleep", "nap"):
        return {"place": {"id": "home", "name": "家", "kind": "home", "district": ""}, "room": {"id": "bedroom", "name": "卧室", "together": False}}
    if activity_id == "eat":
        return {"place": {"id": "home", "name": "家", "kind": "home", "district": ""}, "room": {"id": "dining", "name": "餐桌", "together": False}}
    if activity_id == "out":
        return {"place": {"id": "outside", "name": "附近", "kind": "out", "district": ""}, "room": {"id": "outside", "name": "外面", "together": False}}
    if activity_id == "study":
        return {"place": {"id": "home", "name": "家", "kind": "home", "district": ""}, "room": {"id": "study", "name": "书房", "together": False}}
    return {"place": {"id": "home", "name": "家", "kind": "home", "district": ""}, "room": {"id": "living", "name": "客厅", "together": False}}


def tick(store: Store, now=None):
    now = time.time() if now is None else float(now)
    state = store.read("rhythm/state.json", {}) or {}
    activity = state.get("activity") if isinstance(state.get("activity"), dict) else {}
    expected = activity.get("expected_end")
    changed = False
    if expected and now >= float(expected):
        old = activity.get("id") or "idle"
        history = state.get("history") if isinstance(state.get("history"), list) else []
        history = history[-48:] + [{"id": old, "to": int(now)}]
        new_id, new_label, duration = _next_activity(now)
        state["activity"] = {
            "id": new_id,
            "label": new_label,
            "started": int(now),
            "expected_end": int(now) + duration,
            "with_owner": False,
            "deep": new_id in ("sleep", "nap"),
        }
        state["history"] = history
        state["updated_at"] = int(now)
        store.write("rhythm/state.json", state)
        room = _room_for(new_id)
        now_data = store.read("now.json", {}) or {}
        now_data.update({"place": room["place"], "room": room["room"], "updated_at": int(now)})
        store.write("now.json", now_data)
        store.append_jsonl("timeline/%s.jsonl" % datetime.fromtimestamp(now).strftime("%Y-%m-%d"), {
            "ts": int(now),
            "kind": "rhythm",
            "text": "%s -> %s" % (old, new_id),
        })
        changed = True

    mood = store.read("mood.json", {}) or {}
    value = mood.get("value")
    ts = mood.get("ts")
    try:
        value = float(value)
        ts = float(ts)
    except (TypeError, ValueError):
        value = None
    if value is not None and ts:
        hours = max(0.0, now - ts) / 3600.0
        decayed = 0.62 + (value - 0.62) * (0.5 ** (hours / 2.0))
        if abs(decayed - value) > 0.0005:
            store.write("mood.json", {"value": round(decayed, 4), "baseline": 0.62, "ts": int(now)})
            changed = True

    today = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
    life = store.read("her_life.json", {}) or {}
    if life.get("date") != today:
        store.write("her_life.json", {"date": today, "events": [], "discovery": ""})
        changed = True
    return changed
