# -*- coding: utf-8 -*-
"""Chat -> state bridge. No LLM calls; only local JSON/SQLite updates."""
from __future__ import annotations

import time
from datetime import datetime

from .growth import maybe_add_first
from .memory import append_memory
from .store import Store

POSITIVE = ("喜欢", "想你", "爱你", "抱", "亲", "乖", "可爱", "辛苦", "谢谢", "夸", "好棒", "开心")
NEGATIVE = ("累", "烦", "难过", "生气", "委屈", "对不起", "讨厌", "滚")


def _clamp(value):
    return max(0.0, min(1.0, value))


def _bump_mood(store, now, delta):
    mood = store.read("mood.json", {}) or {}
    try:
        value = float(mood.get("value"))
    except (TypeError, ValueError):
        value = 0.62
    value = _clamp(value + delta)
    store.write("mood.json", {"value": round(value, 4), "baseline": 0.62, "ts": int(now)})
    return value


def _set_chat_activity(store, now):
    state = store.read("rhythm/state.json", {}) or {}
    old = state.get("activity") if isinstance(state.get("activity"), dict) else {}
    history = state.get("history") if isinstance(state.get("history"), list) else []
    history = history[-48:] + [{"id": old.get("id") or "idle", "to": int(now)}]
    state["activity"] = {
        "id": "chat_together",
        "label": "陪你聊天",
        "started": int(now),
        "expected_end": int(now + 10 * 60),
        "with_owner": True,
        "deep": False,
    }
    state["with_owner"] = True
    state["history"] = history
    state["updated_at"] = int(now)
    store.write("rhythm/state.json", state)

    now_data = store.read("now.json", {}) or {}
    place = now_data.get("place") if isinstance(now_data.get("place"), dict) else {}
    if place.get("kind") != "out":
        now_data["place"] = {"id": "home", "name": "家", "kind": "home", "district": ""}
        now_data["room"] = {"id": "living", "name": "客厅", "together": True}
    now_data["updated_at"] = int(now)
    store.write("now.json", now_data)


def _touch_life(store, now):
    today = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
    life = store.read("her_life.json", {}) or {}
    if life.get("date") != today:
        life = {"date": today, "events": [], "discovery": ""}
    events = [str(item) for item in (life.get("events") or []) if str(item).strip()]
    if "和你说了一会儿话" not in events:
        events.append("和你说了一会儿话")
    life["events"] = events[-3:]
    life["date"] = today
    store.write("her_life.json", life)


def _touch_emotion(store, now, positive):
    emo = store.read("emotion/emotion.json", {}) or {}
    values = emo.get("e") if isinstance(emo.get("e"), dict) else {}
    happy = values.get("开心") if isinstance(values.get("开心"), dict) else {}
    happy["i"] = round(_clamp(float(happy.get("i") or 0.0) + (0.08 if positive else 0.03)), 3)
    happy["t"] = int(now)
    happy["cause"] = "对话"
    happy["n"] = int(happy.get("n") or 0) + 1
    values["开心"] = happy
    if positive:
        shy = values.get("羞") if isinstance(values.get("羞"), dict) else {}
        shy["i"] = round(_clamp(float(shy.get("i") or 0.0) + 0.03), 3)
        shy["t"] = int(now)
        shy["cause"] = "被夸"
        shy["n"] = int(shy.get("n") or 0) + 1
        values["羞"] = shy
    emo["e"] = values
    emo["ts"] = int(now)
    store.write("emotion/emotion.json", emo)

    at = datetime.fromtimestamp(now).strftime("%H:%M")
    store.append_jsonl("emotion/shadow.jsonl", {
        "ts": int(now),
        "at": at,
        "kind": "chat",
        "cause": "对话",
        "n": 1,
        "i": round(0.5 if positive else 0.3, 3),
        "e": {
            "开心": round(float(values.get("开心", {}).get("i") or 0.0), 3),
            "羞": round(float(values.get("羞", {}).get("i") or 0.0), 3),
        },
        "would": "",
    })


def on_message(store: Store, text_value, is_owner=True, now=None,
               remember=True, growth=True, memory_interval=120):
    """Update mood/activity/emotion/today/memory from one real owner message."""
    text_value = (text_value or "").strip()
    if not text_value:
        return {}
    if not is_owner:
        return {}
    now = time.time() if now is None else float(now)
    positive = any(word in text_value for word in POSITIVE)
    negative = any(word in text_value for word in NEGATIVE)
    delta = 0.02 if positive else (-0.01 if negative else 0.004)

    mood = _bump_mood(store, now, delta)
    _set_chat_activity(store, now)
    _touch_life(store, now)
    _touch_emotion(store, now, positive)
    store.append_jsonl("timeline/%s.jsonl" % datetime.fromtimestamp(now).strftime("%Y-%m-%d"), {
        "ts": int(now),
        "kind": "chat",
        "text": "对话",
    })

    memory_item = None
    chat_state = store.read("chat_state.json", {}) or {}
    try:
        last_memory = float(chat_state.get("last_memory_at") or 0)
    except (TypeError, ValueError):
        last_memory = 0
    if remember and len(text_value) >= 4 and now - last_memory >= max(10, int(memory_interval)):
        memory_item = append_memory(store, "你说：" + text_value[:140], kind="事件", tags=["对话"], now=now)
        store.write("chat_state.json", {"last_memory_at": int(now)})

    growth_key = maybe_add_first(store, text_value, now) if growth else None
    return {
        "mood": mood,
        "positive": positive,
        "negative": negative,
        "memory": memory_item is not None,
        "growth": growth_key,
    }
