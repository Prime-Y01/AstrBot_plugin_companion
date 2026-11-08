# -*- coding: utf-8 -*-
"""Generic memory export adapter (v3). No database, no livingmemory."""
from __future__ import annotations

import time
from datetime import datetime

from .store import Store


def iso(ts):
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def _empty():
    return {
        "version": 3,
        "generated_at": iso(time.time()),
        "items": [],
        "stats": {
            "total": 0,
            "daily": {},
            "top_recalled": [],
            "recalled_at": "",
            "event_at_missing": 0,
            "source_time_missing": 0,
            "by_kind": {},
            "export_ms": 0,
        },
    }


def load_export(store: Store):
    payload = store.read("exports/memory_export.json", None)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        payload = _empty()
    payload.setdefault("version", 3)
    payload.setdefault("items", [])
    payload.setdefault("stats", {})
    return payload


def append_memory(store: Store, text_value, kind="事件", tags=None, now=None, source="chat"):
    """Append one v3 memory item and refresh stats. Returns the item or None."""
    text_value = (text_value or "").strip()
    if not text_value:
        return None
    now = time.time() if now is None else float(now)
    payload = load_export(store)
    items = payload["items"]
    next_id = 1
    for item in items:
        try:
            next_id = max(next_id, int(item.get("id") or 0) + 1)
        except (TypeError, ValueError):
            continue
    event_at = iso(now)
    item = {
        "id": next_id,
        "text": text_value[:160],
        "kind": kind or "事件",
        "tags": [str(tag)[:20] for tag in (tags or ["对话"]) if str(tag).strip()][:6],
        "created_at": event_at,
        "event_at": event_at,
        "event_date": datetime.fromtimestamp(now).strftime("%Y-%m-%d"),
        "event_precision": "datetime",
        "refs": {
            "source_time_start": event_at,
            "source_time_end": event_at,
            "pinned": False,
            "source": source,
        },
    }
    items.append(item)
    stats = payload.setdefault("stats", {})
    stats["total"] = len(items)
    stats["daily"] = {}
    stats["by_kind"] = {}
    for row in items:
        day = str(row.get("event_date") or "")
        if day:
            stats["daily"][day] = stats["daily"].get(day, 0) + 1
        kind_value = str(row.get("kind") or "其他")
        stats["by_kind"][kind_value] = stats["by_kind"].get(kind_value, 0) + 1
    stats.setdefault("top_recalled", [])
    stats.setdefault("recalled_at", "")
    stats["event_at_missing"] = 0
    stats["source_time_missing"] = 0
    payload["version"] = 3
    payload["generated_at"] = iso(now)
    store.write("exports/memory_export.json", payload)
    return item
