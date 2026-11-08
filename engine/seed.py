# -*- coding: utf-8 -*-
"""Seed a fresh, generic data directory. No personal data is included."""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta

from .store import Store

DEFAULT_PROFILE = {
    "profile": {
        "her_name": "她",
        "owner_name": "你",
        "title": "予其真实",
        "subtitle": "COMPANION · STATE",
    },
    "features": {
        "memory": True,
        "memory_edit": False,
        "sim": True,
        "commands": True,
    },
}

DEMO_MEMORIES = [
    ("你把伞放在门口，说今天可能下雨", "事件", ["照顾", "天气"]),
    ("我在窗边看了一会儿雨，玻璃上全是水珠", "其他", ["日常", "天气"]),
    ("你回来得比平时晚，我把饭又热了一遍", "事件", ["等你", "吃饭"]),
    ("第一次一起把一整部电影看完", "事实", ["第一次", "一起"]),
    ("你夸我新换的床单颜色好看", "其他", ["被夸", "家里"]),
    ("下午犯困，趴在桌上睡了二十分钟", "事件", ["午睡", "日常"]),
    ("你说周末想去海边，我记下了", "计划", ["约定", "出门"]),
    ("我把你上次落下的耳机收进了抽屉", "事件", ["收拾", "你"]),
    ("今天不想说话，只回了几个字", "其他", ["情绪", "安静"]),
    ("你问我是不是累了，我说有一点", "事件", ["被关心", "累"]),
    ("第一次自己煮了面，味道还行", "事实", ["第一次", "做饭"]),
    ("窗台上的绿萝长出新叶子", "其他", ["植物", "日常"]),
    ("你发来一张路上的晚霞，我存下来了", "事件", ["照片", "晚霞"]),
    ("晚上一起听歌，谁也没先说话", "其他", ["一起", "安静"]),
    ("我说想去看海，你说等天气暖一点", "计划", ["约定", "海"]),
    ("你出门前摸了摸我的头", "事件", ["亲近", "出门"]),
    ("把房间收拾了一遍，心情好了一点", "事件", ["收拾", "心情"]),
    ("今天学了一首新歌，副歌还没唱顺", "其他", ["唱歌", "练习"]),
    ("你半夜回来，我给你留了一盏灯", "事件", ["等你", "夜里"]),
    ("第一次收到你写的小纸条", "事实", ["第一次", "礼物"]),
    ("下雨天不想出门，窝在沙发上发呆", "其他", ["雨天", "发呆"]),
    ("你说明天要早起，我定了闹钟", "计划", ["早起", "照顾"]),
    ("我把今天的天气写进了日记", "其他", ["日记", "天气"]),
    ("你道歉的时候，我其实已经不那么生气了", "事件", ["道歉", "情绪"]),
    ("第一次一起做饭，厨房有点乱", "事实", ["第一次", "做饭"]),
    ("你说我穿这件外套好看", "其他", ["被夸", "衣服"]),
    ("晚上看了两集动画，片尾曲很好听", "事件", ["看番", "晚上"]),
    ("把想买的东西列了个清单，又划掉一半", "其他", ["计划", "购物"]),
    ("你问我明天想做什么，我说还没想好", "事件", ["聊天", "明天"]),
    ("今天过得很慢，但也不坏", "其他", ["日常", "心情"]),
]

DEMO_MILESTONES = [
    ("第一次一起看电影", "first_movie", "first"),
    ("第一次一起做饭", "first_cook", "first"),
    ("第一次收到你的礼物", "first_gift", "first"),
    ("第一次一起看海", "first_sea", "first"),
    ("第一次吵架又和好", "first_fight", "first"),
    ("第一次一起过生日", "first_birthday", "first"),
    ("第一次一起旅行", "first_trip", "first"),
    ("第一次说“我们”", "first_us", "first"),
]


def iso(ts):
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def _activity(now, demo):
    hour = datetime.fromtimestamp(now).hour
    if not demo:
        return {
            "id": "idle",
            "label": "发呆",
            "started": int(now) - 600,
            "expected_end": 0,
            "with_owner": False,
            "deep": False,
        }
    if hour < 7:
        return {"id": "sleep", "label": "睡觉", "started": int(now) - 3600, "expected_end": int(now) + 3 * 3600, "with_owner": False, "deep": True}
    if hour < 9:
        return {"id": "eat", "label": "吃饭", "started": int(now) - 900, "expected_end": int(now) + 1200, "with_owner": False, "deep": False}
    if hour < 12:
        return {"id": "study", "label": "看书", "started": int(now) - 1800, "expected_end": int(now) + 2700, "with_owner": False, "deep": False}
    if hour < 13:
        return {"id": "eat", "label": "吃饭", "started": int(now) - 600, "expected_end": int(now) + 900, "with_owner": False, "deep": False}
    if hour < 15:
        return {"id": "nap", "label": "午睡", "started": int(now) - 1200, "expected_end": int(now) + 2400, "with_owner": False, "deep": True}
    if hour < 18:
        return {"id": "draw", "label": "画画", "started": int(now) - 2400, "expected_end": int(now) + 3000, "with_owner": False, "deep": False}
    if hour < 19:
        return {"id": "out", "label": "出门", "started": int(now) - 1200, "expected_end": int(now) + 1800, "with_owner": False, "deep": False}
    if hour < 21:
        return {"id": "eat", "label": "吃饭", "started": int(now) - 900, "expected_end": int(now) + 1200, "with_owner": False, "deep": False}
    if hour < 23:
        return {"id": "watch", "label": "看番", "started": int(now) - 1800, "expected_end": int(now) + 3600, "with_owner": False, "deep": False}
    return {"id": "sleep", "label": "睡觉", "started": int(now) - 1200, "expected_end": int(now) + 7 * 3600, "with_owner": False, "deep": True}


def _room_for(activity):
    aid = activity["id"]
    if aid in ("sleep", "nap"):
        return {"place": {"id": "home", "name": "家", "kind": "home", "district": ""}, "room": {"id": "bedroom", "name": "卧室", "together": False}}
    if aid == "eat":
        return {"place": {"id": "home", "name": "家", "kind": "home", "district": ""}, "room": {"id": "dining", "name": "餐桌", "together": False}}
    if aid == "out":
        return {"place": {"id": "outside", "name": "附近", "kind": "out", "district": ""}, "room": {"id": "outside", "name": "外面", "together": False}}
    if aid == "study":
        return {"place": {"id": "home", "name": "家", "kind": "home", "district": ""}, "room": {"id": "study", "name": "书房", "together": False}}
    return {"place": {"id": "home", "name": "家", "kind": "home", "district": ""}, "room": {"id": "living", "name": "客厅", "together": False}}


def _wardrobe_for(activity):
    aid = activity["id"]
    if aid == "sleep":
        occasion, outer = "sleep", "棉质睡裙"
    elif aid == "out":
        occasion, outer = "out", "米色针织开衫 + 浅色长裤"
    else:
        occasion, outer = "home", "浅灰家居服 + 米色开衫"
    return {
        "current": {
            "occasion": occasion,
            "outer": outer,
            "inner": "裸色无痕",
            "accessories": ["细项链"] if occasion == "out" else [],
        },
        "clothes_home": "浅灰家居服 + 米色开衫",
        "clothes_out": "米色针织开衫 + 浅色长裤",
        "clothes_sleep": "棉质睡裙",
        "updated_at": int(time.time()),
    }


def _seed_memories(store, now, demo):
    items = []
    if demo:
        for index, (text, kind, tags) in enumerate(DEMO_MEMORIES):
            event_ts = int(now) - (index + 1) * 7 * 3600 - 600
            created_ts = event_ts + 420
            items.append({
                "id": 1000 + index,
                "text": text,
                "kind": kind,
                "tags": tags,
                "created_at": iso(created_ts),
                "event_at": iso(event_ts),
                "event_date": datetime.fromtimestamp(event_ts).strftime("%Y-%m-%d"),
                "event_precision": "datetime",
                "refs": {
                    "source_time_start": iso(event_ts),
                    "source_time_end": iso(event_ts),
                    "pinned": index % 9 == 0,
                },
            })
    stats = {
        "total": len(items),
        "daily": {},
        "top_recalled": [],
        "recalled_at": "",
        "event_at_missing": 0,
        "source_time_missing": 0,
        "by_kind": {},
        "export_ms": 0,
    }
    for item in items:
        day = item["event_date"]
        stats["daily"][day] = stats["daily"].get(day, 0) + 1
        stats["by_kind"][item["kind"]] = stats["by_kind"].get(item["kind"], 0) + 1
    payload = {
        "version": 3,
        "generated_at": iso(now),
        "items": items,
        "stats": stats,
    }
    store.write_if_missing("exports/memory_export.json", payload)


def _seed_growth(store, now, demo):
    path = store.path("growth/growth.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "create table if not exists milestones ("
            "id integer primary key autoincrement, ts integer, text text, key text, "
            "kind text, source text, created integer, status text)"
        )
        if demo and con.execute("select count(*) from milestones").fetchone()[0] == 0:
            for index, (text, key, kind) in enumerate(DEMO_MILESTONES):
                ts = int(now) - (index + 2) * 86400 * 4
                con.execute(
                    "insert into milestones (ts, text, key, kind, source, created, status) "
                    "values (?, ?, ?, ?, ?, ?, ?)",
                    (ts, text, key, kind, "demo", int(now), "active"),
                )
        con.commit()
    finally:
        con.close()


def _seed_emotion(store, now, demo):
    if demo:
        events = []
        for hours_ago in range(24, 0, -2):
            ts = int(now) - hours_ago * 3600
            values = {
                "开心": max(0.0, min(1.0, 0.45 + 0.25 * __import__("math").sin(hours_ago / 3.0))),
                "羞": 0.10 if hours_ago % 6 else 0.20,
                "得意": 0.08,
                "恼": 0.04 if hours_ago % 8 else 0.12,
                "委屈": 0.03,
                "失落": 0.05 if hours_ago % 10 else 0.15,
                "怕": 0.02,
            }
            events.append({
                "ts": ts,
                "at": datetime.fromtimestamp(ts).strftime("%H:%M"),
                "kind": "care" if hours_ago % 6 == 0 else "daily",
                "cause": "日常",
                "n": 1,
                "i": round(0.2 + 0.5 * abs(__import__("math").sin(hours_ago / 5.0)), 3),
                "e": {key: round(value, 3) for key, value in values.items()},
                "would": "",
            })
        path = store.path("emotion/shadow.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        current = {
            "e": {
                "开心": {"i": 0.52, "t": int(now) - 1200, "cause": "今天天气不错", "n": 2},
                "羞": {"i": 0.12, "t": int(now) - 2400, "cause": "被夸", "n": 1},
                "得意": {"i": 0.08, "t": int(now) - 4800, "cause": "", "n": 0},
                "恼": {"i": 0.04, "t": int(now) - 3600, "cause": "", "n": 0},
                "委屈": {"i": 0.03, "t": int(now) - 7200, "cause": "", "n": 0},
                "失落": {"i": 0.06, "t": int(now) - 7200, "cause": "", "n": 0},
                "怕": {"i": 0.02, "t": int(now) - 7200, "cause": "", "n": 0},
            },
            "ts": int(now),
        }
        store.write_if_missing("emotion/emotion.json", current)
    else:
        store.write_if_missing("emotion/emotion.json", {"e": {}, "ts": int(now)})


def _seed_life(store, now, demo):
    today = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
    if demo:
        data = {
            "date": today,
            "events": ["把窗打开了一点，风是凉的", "给绿萝换了水", "翻了两页没看完的书"],
            "discovery": "楼下新开了一家面包店",
        }
    else:
        data = {"date": today, "events": [], "discovery": ""}
    store.write_if_missing("her_life.json", data)


def _seed_demo_state(store, now):
    activity = _activity(now, True)
    place = _room_for(activity)
    history = []
    for index, activity_id in enumerate(("sleep", "eat", "study", "eat", "nap", "draw")):
        history.append({"id": activity_id, "to": int(now) - (6 - index) * 3600})
    state = {
        "activity": activity,
        "with_owner": False,
        "history": history,
        "updated_at": int(now),
    }
    store.write_if_missing("rhythm/state.json", state)
    store.write_if_missing("rhythm/body.json", {
        "phase": "follicular",
        "day": 8,
        "period": 5,
        "start": int(now) - 8 * 86400,
        "length": 28,
        "energy": 0.72,
        "pain": 0.08,
        "libido": 0.35,
    })
    store.write_if_missing("mood.json", {"value": 0.70, "baseline": 0.62, "ts": int(now) - 600})
    store.write_if_missing("now.json", {
        "place": place["place"],
        "room": place["room"],
        "updated_at": int(now),
    })
    store.write_if_missing("wardrobe.json", _wardrobe_for(activity))
    store.write_if_missing("reality.json", {
        "weather": {"text": "晴 22°C", "desc": "晴"},
        "city": "",
        "updated_at": int(now),
    })


def _seed_empty_state(store, now):
    activity = _activity(now, False)
    place = _room_for(activity)
    store.write_if_missing("rhythm/state.json", {
        "activity": activity,
        "with_owner": False,
        "history": [],
        "updated_at": int(now),
    })
    store.write_if_missing("rhythm/body.json", {
        "phase": "follicular",
        "day": 8,
        "period": 5,
        "start": int(now) - 8 * 86400,
        "length": 28,
        "energy": 0.70,
        "pain": 0.10,
        "libido": 0.30,
    })
    store.write_if_missing("mood.json", {"value": 0.62, "baseline": 0.62, "ts": int(now)})
    store.write_if_missing("now.json", {
        "place": place["place"],
        "room": place["room"],
        "updated_at": int(now),
    })
    store.write_if_missing("wardrobe.json", _wardrobe_for(activity))
    store.write_if_missing("reality.json", {
        "weather": {"text": "", "desc": ""},
        "city": "",
        "updated_at": int(now),
    })


def seed(data_dir, demo=True, now=None, profile=None, features=None):
    """Create missing files only; safe to call on every plugin start."""
    store = Store(data_dir)
    now = time.time() if now is None else float(now)
    for rel in ("rhythm", "emotion", "growth", "exports", "ui_commands/done", "timeline", "panel_logs", "panel_cache"):
        store.path(rel).mkdir(parents=True, exist_ok=True)

    profile_payload = json.loads(json.dumps(DEFAULT_PROFILE))
    if isinstance(profile, dict):
        profile_payload["profile"].update({key: str(value) for key, value in profile.items() if value})
    if isinstance(features, dict):
        profile_payload["features"].update({key: bool(value) for key, value in features.items()})
    store.write_if_missing("panel_profile.json", profile_payload)

    if demo:
        _seed_demo_state(store, now)
    else:
        _seed_empty_state(store, now)
    _seed_emotion(store, now, demo)
    _seed_life(store, now, demo)
    _seed_memories(store, now, demo)
    _seed_growth(store, now, demo)
    day = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
    timeline = store.path("timeline") / (day + ".jsonl")
    if not timeline.exists():
        store.append_jsonl("timeline/" + day + ".jsonl", {
            "ts": int(now),
            "kind": "seed",
            "text": "数据初始化",
        })
    return store
