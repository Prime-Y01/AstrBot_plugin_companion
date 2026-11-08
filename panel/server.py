#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""予其真实 · 只读可视化面板（开源插件版）

数据目录由 `--data-dir` 指定（插件默认用 AstrBot 的 plugin_data 目录）。
面板只读状态文件；唯一写路径是 `data/ui_commands/`（命令队列）和本地面板缓存。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
DATA = ROOT / "data"
CACHE = DATA / "panel_cache"
LOGS = DATA / "panel_logs"

HOST = "127.0.0.1"
PORT = 8765
SCHEMA = 1

PROFILE = {
    "her_name": "她",
    "owner_name": "你",
    "title": "予其真实",
    "subtitle": "COMPANION · STATE",
}
FEATURES = {
    "memory": True,
    "memory_edit": False,
    "sim": True,
    "commands": True,
}


# ---- 情绪（与 scripts/emotion.py 对齐，只读镜像；不改它） -------------------
EMOTIONS = ("开心", "羞", "得意", "恼", "委屈", "失落", "怕")
HALF_LIFE = {
    "恼": 3.5 * 60,
    "羞": 3.5 * 60,
    "怕": 3.5 * 60,
    "得意": 8 * 60,
    "委屈": 10 * 60,
    "失落": 10 * 60,
    "开心": 20 * 60,
}
FLOOR = 0.02
EVENT_LABELS = {
    "praised": "他夸她",
    "apology": "他道歉",
    "coaxed": "他哄她",
    "teased": "他逗她",
    "banter": "斗嘴",
    "care": "他照顾她",
}
EMOTION_COLORS = {
    "开心": "#b8860b",
    "羞": "#c25a7a",
    "得意": "#6b4fd8",
    "恼": "#d9543a",
    "委屈": "#2f6feb",
    "失落": "#6b7c88",
    "怕": "#7a5cd6",
}

# ---- 活动（显示用，数据仍以 rhythm/state.json 的 label 为准） --------------
ACTIVITY = {
    "sleep": ("睡觉", "睡着", "睡着", "#2f6feb"),
    "nap": ("午睡", "打盹", "打盹", "#2f6feb"),
    "eat": ("吃饭", "在吃饭", "吃饭", "#b8860b"),
    "cook": ("做饭", "在做饭", "做饭", "#b8860b"),
    "draw": ("画画", "在画画", "画画", "#0a9f96"),
    "study": ("看书", "在看书", "看书", "#2f6feb"),
    "watch": ("看番", "在看番", "看番", "#2f6feb"),
    "screen": ("刷手机", "在刷手机", "刷手机", "#6b7c88"),
    "out": ("出门", "在外面", "在外面", "#0a9f96"),
    "errand": ("散步取快递", "在办事", "办事", "#0a9f96"),
    "sing": ("学歌", "在唱歌", "唱歌", "#c25a7a"),
    "bath": ("洗澡护肤", "在洗澡", "洗澡", "#2f6feb"),
    "tidy": ("收拾房间", "在收拾", "收拾房间", "#6b8f5a"),
    "idle": ("发呆", "在发呆", "发呆", "#6b7c88"),
    "intimacy": ("亲热", "和你在一起", "和你在一起", "#c25a7a"),
    "sit": ("陪你坐着", "陪着你", "陪着你", "#c25a7a"),
    "lie": ("陪你躺着", "陪着你", "陪着你", "#c25a7a"),
    "cuddle": ("窝在毯子里陪你", "陪着你", "陪着你", "#c25a7a"),
    "chat_together": ("陪你聊天", "陪着你", "陪着你", "#c25a7a"),
    "hug": ("抱着你", "抱着你", "抱着你", "#c25a7a"),
    "lean": ("靠着你", "靠着你", "靠着你", "#c25a7a"),
    "hand": ("牵着你", "牵着你", "牵着你", "#c25a7a"),
    "together_idle": ("陪你发呆", "陪着你", "陪着你", "#c25a7a"),
    "game": ("打游戏", "在打游戏", "打游戏", "#7a5cd6"),
    "piano": ("练琴", "在练琴", "练琴", "#7a5cd6"),
}
DEFAULT_ACT = ("在做点什么", "在做点什么", "在做点什么", "#0a9f96")
TOGETHER_IDS = {
    "sit", "lie", "cuddle", "chat_together", "hug", "lean", "hand",
    "together_idle", "intimacy",
}
KIND_LABELS = {
    "first": "第一次",
    "relationship": "关系",
    "habit": "习惯",
    "refusal": "说不",
    "invite": "约他",
    "work": "作品",
    "pin": "他记下",
}
WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
WEATHER_WORDS = (
    "雷阵雨", "毛毛雨", "大暴雨", "小到中雨", "中到大雨", "暴雨", "大雨",
    "中雨", "小雨", "阵雨", "雨", "小雪", "中雪", "大雪", "雪", "多云",
    "晴", "阴", "雾", "霾", "风",
)

# ---- 小工具 ----------------------------------------------------------------
_LOG_LOCK = threading.Lock()


def log(message):
    """写面板自己的日志（只写数据目录下的 panel_logs/）。"""
    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        path = LOGS / "panel.log"
        if path.exists() and path.stat().st_size > 512 * 1024:
            try:
                os.replace(str(path), str(path) + ".1")
            except OSError:
                pass
        line = "%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message)
        with _LOG_LOCK:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
    except Exception:  # noqa: BLE001 - 日志失败不许影响面板
        pass


def _load_profile(path=None):
    """读 panel_profile.json：名字、标题、功能开关。"""
    path = Path(path) if path else DATA / "panel_profile.json"
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            cfg = json.load(fh)
    except FileNotFoundError:
        return
    except Exception as exc:  # noqa: BLE001
        log("profile load failed: %s" % exc)
        return
    if not isinstance(cfg, dict):
        return
    if isinstance(cfg.get("profile"), dict):
        for key in ("her_name", "owner_name", "title", "subtitle"):
            value = cfg["profile"].get(key)
            if isinstance(value, str) and value.strip():
                PROFILE[key] = value.strip()[:40]
    if isinstance(cfg.get("features"), dict):
        for key in ("memory", "memory_edit", "sim", "commands"):
            if key in cfg["features"]:
                FEATURES[key] = bool(cfg["features"][key])


def _set_data_dir(path, runtime_dir=None, profile_path=None):
    """切换状态目录；缓存/日志可放到单独的 runtime 目录。"""
    global DATA, CACHE, LOGS
    DATA = Path(path).resolve()
    runtime = Path(runtime_dir).resolve() if runtime_dir else DATA
    CACHE = runtime / "panel_cache"
    LOGS = runtime / "panel_logs"
    _load_profile(profile_path)


def clamp01(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:  # NaN
        return None
    return max(0.0, min(1.0, out))


def num(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def text(value):
    return value if isinstance(value, str) else ""


def read_json(relpath, default=None):
    """只读一个 JSON；失败返回 default，永不抛异常。"""
    path = DATA / relpath
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except Exception as exc:  # noqa: BLE001
        log("read_json %s failed: %s" % (relpath, exc))
        return default


def file_age(relpath, now):
    try:
        return max(0.0, float(now) - (DATA / relpath).stat().st_mtime)
    except OSError:
        return None


def fmt_age(seconds):
    if seconds is None:
        return "未更新"
    if seconds < 90:
        return "刚刚"
    if seconds < 3600:
        return "%d 分钟前" % int(seconds // 60)
    if seconds < 86400:
        return "%.1f 小时前" % (seconds / 3600.0)
    return "%.1f 天前" % (seconds / 86400.0)


def fmt_span(seconds):
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60
    if hours:
        return "%d 小时 %d 分" % (hours, minutes)
    return "%d 分钟" % max(1, minutes)


def parse_weather(reality):
    raw = ""
    if isinstance(reality, dict):
        weather = reality.get("weather")
        if isinstance(weather, dict):
            raw = text(weather.get("text"))
    if not raw:
        return {"raw": "", "text": "", "desc": "", "temp": None, "district": ""}
    temp = None
    match = re.search(r"(-?\d+)\s*°?\s*C", raw)
    if match:
        temp = int(match.group(1))
    desc = ""
    for word in WEATHER_WORDS:
        if word in raw:
            desc = word
            break
    district = ""
    district_match = re.search(r"市([\u4e00-\u9fa5]{2,5}?)区", raw)
    if district_match:
        district = district_match.group(1)
    short = desc or ""
    if temp is not None:
        short = (short + " " if short else "") + "%d°" % temp
    return {
        "raw": raw,
        "text": short.strip(),
        "desc": desc,
        "temp": temp,
        "district": district,
    }


def activity_meta(activity_id):
    return ACTIVITY.get(activity_id, DEFAULT_ACT)


def strip_room(name):
    """「卧室（她的）」->「卧室」；显示用，不改数据。"""
    name = text(name) or "房间"
    return re.sub(r"[（(].*?[)）]", "", name).strip() or name


# ---- 此刻 ------------------------------------------------------------------
def build_activity(rhythm, now):
    act = rhythm.get("activity") if isinstance(rhythm, dict) else None
    act = act if isinstance(act, dict) else {}
    activity_id = text(act.get("id")) or "idle"
    label, display, verb, color = activity_meta(activity_id)
    label = text(act.get("label")) or label
    if not bool(act.get("with_owner")):
        _solo = {"lie": "躺着", "cuddle": "窝着", "sit": "坐着", "together_idle": "发呆", "chat_together": "自己待着"}
        if activity_id in _solo:
            label = display = verb = _solo[activity_id]
    started = num(act.get("started"))
    expected = num(act.get("expected_end"))
    remaining = None
    progress = None
    if expected and expected > 0:
        remaining = expected - now
        if started and expected > started:
            progress = clamp01((now - started) / (expected - started))
    if remaining is None:
        remaining_text = ""
    elif remaining <= 0:
        remaining_text = "等着换下一段"
    else:
        remaining_text = "还剩 " + fmt_span(remaining)
    elapsed = "%s" % fmt_span(now - started) if started else ""
    return {
        "id": activity_id,
        "label": label,
        "display": display,
        "verb": verb,
        "color": color,
        "with_owner": bool(rhythm.get("with_owner")) if isinstance(rhythm, dict) else False,
        "started": started,
        "expected_end": expected,
        "started_text": datetime.fromtimestamp(started).strftime("%H:%M") if started else "",
        "elapsed_text": elapsed,
        "remaining_seconds": remaining,
        "remaining_text": remaining_text,
        "progress": progress,
    }


def build_room(now_json):
    room = now_json.get("room") if isinstance(now_json, dict) else None
    room = room if isinstance(room, dict) else {}
    place = now_json.get("place") if isinstance(now_json, dict) else None
    place = place if isinstance(place, dict) else {}
    at_home = text(place.get("kind")) == "home"
    room_name = text(room.get("name"))
    if not at_home:
        room_name = text(place.get("name")) or "外面"
    elif not room_name:
        room_name = "家里"
    return {
        "id": text(room.get("id")),
        "name": room_name or "——",
        "short": strip_room(text(room.get("name"))),
        "together": bool(room.get("together")),
        "place_name": text(place.get("name")),
        "place_kind": text(place.get("kind")),
        "district": text(place.get("district")),
        "at_home": text(place.get("kind")) == "home",
    }


def build_outfit(wardrobe):
    if not isinstance(wardrobe, dict):
        return {"text": "——", "occasion": "", "occasion_label": "", "accessories": ""}
    current = wardrobe.get("current") if isinstance(wardrobe.get("current"), dict) else {}
    occasion = text(current.get("occasion"))
    outer = text(current.get("outer"))
    if not outer:
        key = {"home": "clothes_home", "out": "clothes_out", "sleep": "clothes_sleep"}.get(occasion)
        outer = text(wardrobe.get(key)) if key else ""
    accessories = current.get("accessories")
    if isinstance(accessories, list):
        accessories = "、".join(text(item) for item in accessories if text(item))
    else:
        accessories = text(accessories)
    occasion_label = {"home": "在家", "out": "出门", "sleep": "睡觉"}.get(occasion, "")
    return {
        "text": outer or "——",
        "occasion": occasion,
        "occasion_label": occasion_label,
        "accessories": accessories,
        "under": text(current.get("inner")),
    }


def build_mood(mood, now):
    """与 scripts/mood.py 一致：每 2 小时向基线 0.62 靠一半。"""
    if not isinstance(mood, dict):
        return {"value": None, "percent": None, "text": "", "available": False}
    value = num(mood.get("value"))
    if value is None:
        return {"value": None, "percent": None, "text": "", "available": False}
    if 1 < value <= 100:
        value /= 100.0
    value = clamp01(value)
    ts = num(mood.get("ts"))
    if ts:
        hours = max(0.0, now - ts) / 3600.0
        value = clamp01(0.62 + (value - 0.62) * (0.5 ** (hours / 2.0)))
    if value is None:
        return {"value": None, "percent": None, "text": "", "available": False}
    if value < 0.3:
        label = "很低落"
    elif value < 0.5:
        label = "有点累"
    elif value < 0.7:
        label = "还不错"
    else:
        label = "很好"
    return {
        "value": round(value, 3),
        "percent": int(round(value * 100)),
        "text": label,
        "available": True,
    }


def build_body(body, now):
    if not isinstance(body, dict):
        return {"available": False, "energy": None, "libido": None, "pain": None}
    stale = False
    start = num(body.get("start"))
    length = num(body.get("length"))
    if start and length and start <= now:
        day = int((datetime.fromtimestamp(now).date() - datetime.fromtimestamp(start).date()).days) + 1
        if day > int(length):
            stale = True
    energy = None if stale else clamp01(num(body.get("energy")))
    libido = None if stale else clamp01(num(body.get("libido")))
    pain = None if stale else clamp01(num(body.get("pain")))
    return {
        "available": True,
        "stale": stale,
        "energy": energy,
        "libido": libido,
        "pain": pain,
        "energy_percent": int(round(energy * 100)) if energy is not None else None,
        "libido_percent": int(round(libido * 100)) if libido is not None else None,
        "pain_percent": int(round(pain * 100)) if pain is not None else None,
        "phase": text(body.get("phase")),
        "day": num(body.get("day")),
    }


def build_day(rhythm, activity, now):
    """今天的活动条：从 rhythm.history + 当前活动拼，只读。"""
    day_start = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    history = rhythm.get("history") if isinstance(rhythm, dict) else None
    history = history if isinstance(history, list) else []
    rows = []
    for item in history:
        if not isinstance(item, dict):
            continue
        end = num(item.get("to"))
        if end is None or end <= day_start or end > now + 60:
            continue
        rows.append((end, text(item.get("id"))))
    rows.sort(key=lambda pair: pair[0])

    segments = []
    prev_end = None
    for end, activity_id in rows:
        begin = prev_end if prev_end is not None else max(day_start, end - 1800)
        begin = max(day_start, min(begin, end))
        if end - begin >= 30:
            segments.append({"id": activity_id, "start": begin, "end": end})
        prev_end = end

    started = activity.get("started")
    if started and started < now:
        begin = max(day_start, started)
        segments.append({"id": activity["id"], "start": begin, "end": now})

    # 合并相邻同活动
    merged = []
    for seg in segments:
        if merged and merged[-1]["id"] == seg["id"] and abs(merged[-1]["end"] - seg["start"]) < 60:
            merged[-1]["end"] = max(merged[-1]["end"], seg["end"])
        else:
            merged.append(dict(seg))

    out = []
    total = 86400.0  # 全天 24 小时，右边留白 = 还没发生
    for seg in merged:
        label, display, verb, color = activity_meta(seg["id"])
        label = "和你在一起" if seg["id"] in TOGETHER_IDS else label
        out.append({
            "id": seg["id"],
            "label": label,
            "color": color,
            "start": seg["start"],
            "end": seg["end"],
            "left": round((seg["start"] - day_start) / total * 100.0, 3),
            "width": round((seg["end"] - seg["start"]) / total * 100.0, 3),
            "minutes": int(round((seg["end"] - seg["start"]) / 60.0)),
            "start_text": datetime.fromtimestamp(seg["start"]).strftime("%H:%M"),
        })
    slept = sum(seg["minutes"] for seg in out if seg["id"] in ("sleep", "nap"))
    return {
        "day_start": day_start,
        "elapsed_seconds": now - day_start,
        "elapsed_text": fmt_span(now - day_start),
        "segments": out,
        "slept_minutes": slept,
    }


def build_life(now):
    """她今天做过的小事（data/her_life.json，只读；只当天有效）。"""
    raw = read_json("her_life.json", {}) or {}
    today = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
    if text(raw.get("date")) != today:
        return {"available": False, "events": [], "discovery": ""}
    events = []
    for item in raw.get("events") or []:
        item = text(item).strip()
        if item:
            events.append(item[:60])
    return {
        "available": bool(events),
        "events": events[:3],
        "discovery": text(raw.get("discovery"))[:80],
    }


def build_narrative(activity, room, outfit, mood, weather, now):
    """两句人话；只用真实数据，不编。"""
    hour = datetime.fromtimestamp(now).hour
    desc = weather.get("desc") or ""
    if desc in ("毛毛雨", "小雨", "阵雨", "雷阵雨", "中雨", "大雨", "暴雨", "中到大雨", "小到中雨", "雨"):
        lead = "外面下着%s" % desc
    elif desc in ("雪", "小雪", "中雪", "大雪"):
        lead = "外面下着%s" % desc
    elif desc in ("晴",):
        lead = "今天有太阳"
    elif desc in ("多云",):
        lead = "天上有云"
    elif desc in ("阴", "雾", "霾"):
        lead = "天色发灰"
    else:
        lead = "夜深了" if hour < 5 else ("天黑了" if hour >= 20 else "")

    verb = activity.get("verb") or activity.get("display") or ""
    room_short = room.get("short") or "房间"
    if activity.get("id") in ("out", "errand"):
        place = room.get("place_name") or "外面"
        core = "她%s，%s" % (verb, place)
    elif activity.get("id") in TOGETHER_IDS and activity.get("with_owner"):
        core = "她和你在一起"
    else:
        core = "她在%s里%s" % (room_short, verb)
    if lead:
        core = "%s，%s" % (lead, core)
    parts = [core + "。"]

    remaining = activity.get("remaining_seconds")
    if remaining is not None and remaining > 60:
        if activity.get("id") in ("sleep", "nap"):
            parts.append("还有 %s自然醒。" % fmt_span(remaining))
        else:
            parts.append("还有 %s。" % fmt_span(remaining))
    return parts


def build_state(now):
    rhythm = read_json("rhythm/state.json", {}) or {}
    body_raw = read_json("rhythm/body.json", {}) or {}
    now_json = read_json("now.json", {}) or {}
    wardrobe_raw = read_json("wardrobe.json", {}) or {}
    mood_raw = read_json("mood.json", {}) or {}
    reality = read_json("reality.json", {}) or {}

    activity = build_activity(rhythm, now)
    room = build_room(now_json)
    outfit = build_outfit(wardrobe_raw)
    mood = build_mood(mood_raw, now)
    body = build_body(body_raw, now)
    weather = parse_weather(reality)
    day = build_day(rhythm, activity, now)

    # 成长数：只读 growth.db 的副本（build_growth 里做），这里只取计数
    growth = growth_summary(now)

    freshness = {}
    for key, rel in (
        ("rhythm", "rhythm/state.json"),
        ("body", "rhythm/body.json"),
        ("mood", "mood.json"),
        ("wardrobe", "wardrobe.json"),
        ("now", "now.json"),
        ("weather", "reality.json"),
    ):
        age = file_age(rel, now)
        freshness[key] = {"age_seconds": age, "text": fmt_age(age)}

    hour = datetime.fromtimestamp(now).hour
    moment = datetime.fromtimestamp(now)
    return {
        "date": {
            "full": "%d 年 %d 月 %d 日" % (moment.year, moment.month, moment.day),
            "short": moment.strftime("%m.%d"),
            "weekday": WEEKDAYS[moment.weekday()],
            "iso": moment.strftime("%Y-%m-%d"),
        },
        "hour": hour,
        "activity": activity,
        "room": room,
        "outfit": outfit,
        "mood": mood,
        "body": body,
        "weather": weather,
        "day": day,
        "life": build_life(now),
        "growth": {"count": growth.get("count"), "available": growth.get("available")},
        "narrative": build_narrative(activity, room, outfit, mood, weather, now),
        "freshness": freshness,
    }


# ---- 情绪 ------------------------------------------------------------------
def _decay(value, ts, half, now):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    if ts:
        value *= 0.5 ** (max(0.0, now - float(ts)) / half)
    if value < FLOOR:
        return 0.0
    return max(0.0, min(1.0, value))


def read_shadow(now):
    path = DATA / "emotion" / "shadow.jsonl"
    events = []
    first_ts = None
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:  # noqa: BLE001 - 坏行跳过
                    continue
                if not isinstance(item, dict):
                    continue
                ts = num(item.get("ts"))
                if ts is None:
                    continue
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if ts < now - 24 * 3600:
                    continue
                emotions = item.get("e") if isinstance(item.get("e"), dict) else {}
                values = {}
                for name in EMOTIONS:
                    value = clamp01(emotions.get(name))
                    if value:
                        values[name] = round(value, 3)
                events.append({
                    "ts": ts,
                    "at": text(item.get("at")),
                    "kind": text(item.get("kind")),
                    "cause": text(item.get("cause"))[:40],
                    "stimulus": text(item.get("cause")).split(":", 1)[1][:20] if ":" in text(item.get("cause")) else "",
                    "label": EVENT_LABELS.get(text(item.get("kind")), text(item.get("kind"))),
                    "n": num(item.get("n")) or 1,
                    "dom": text(item.get("dom")),
                    "i": round(clamp01(item.get("i")) or 0.0, 3),
                    "e": values,
                    "would": text(item.get("would"))[:80],
                })
    except FileNotFoundError:
        return [], None
    except Exception as exc:  # noqa: BLE001
        log("read shadow failed: %s" % exc)
        return [], None
    events.sort(key=lambda item: item["ts"])
    if len(events) > 200:
        events = events[-200:]
    return events, first_ts


def build_emotions(now):
    state = read_json("emotion/emotion.json", {}) or {}
    if (DATA / "emotion" / "disabled").exists():
        mode = "off"
    elif (DATA / "emotion" / "live").exists():
        mode = "live"
    else:
        mode = "shadow"

    current = {}
    raw = state.get("e") if isinstance(state.get("e"), dict) else {}
    for name in EMOTIONS:
        item = raw.get(name) if isinstance(raw.get(name), dict) else {}
        half = HALF_LIFE[name]
        value = _decay(item.get("i"), item.get("t"), half, now)
        current[name] = {
            "value": round(value, 3),
            "percent": int(round(value * 100)),
            "ts": num(item.get("t")),
            "cause": text(item.get("cause"))[:40],
            "n": num(item.get("n")) or 0,
        }

    events, first_ts = read_shadow(now)
    peak = {name: 0.0 for name in EMOTIONS}
    for event in events:
        for name, value in event["e"].items():
            if name in peak and value > peak[name]:
                peak[name] = value
    top = None
    for event in events:
        if top is None or event["i"] > top["i"]:
            top = event

    # 当前最浓（取 current 最大值）
    strongest = max(EMOTIONS, key=lambda key: current[key]["value"])
    return {
        "mode": mode,
        "mode_label": {"off": "已关闭", "shadow": "影子模式 · 只记不注入", "live": "已接入"}[mode],
        "emotions": [
            {
                "name": name,
                "color": EMOTION_COLORS[name],
                "half_life": HALF_LIFE[name],
                "current": current[name],
                "peak": round(peak[name], 3),
            }
            for name in EMOTIONS
        ],
        "strongest": strongest if current[strongest]["value"] > 0 else "",
        "events": events,
        "top": {
            "ts": top["ts"], "at": top["at"], "name": top["dom"], "i": top["i"],
            "label": top["label"], "stimulus": top["stimulus"], "would": top["would"],
        } if top else None,
        "window": {
            "from": now - 24 * 3600,
            "to": now,
            "coverage_start": max(now - 24 * 3600, first_ts) if first_ts else None,
        },
    }


# ---- 成长（读副本） --------------------------------------------------------
_GROWTH_LOCK = threading.Lock()
_GROWTH_CACHE = {"ts": 0.0, "payload": None}


def _copy_growth_db(src, dst):
    """用 sqlite backup API 从只读连接复制一份一致副本，绝不写源库。"""
    uri = src.as_uri() + "?mode=ro"
    source = sqlite3.connect(uri, uri=True, timeout=2.0)
    try:
        tmp = dst.with_name(dst.name + ".tmp")
        try:
            tmp.unlink()
        except OSError:
            pass
        target = sqlite3.connect(str(tmp))
        try:
            source.backup(target)
        finally:
            target.close()
        os.replace(str(tmp), str(dst))
    finally:
        source.close()


def build_growth(now, force=False):
    with _GROWTH_LOCK:
        cached = _GROWTH_CACHE["payload"]
        if not force and cached and now - _GROWTH_CACHE["ts"] < 5:
            return cached

        src = DATA / "growth" / "growth.db"
        if not src.exists():
            payload = {
                "available": False, "count": None, "items": [], "stale": False,
                "error": "growth.db 不存在", "copied_at": None,
            }
            _GROWTH_CACHE.update({"ts": now, "payload": payload})
            return payload

        cache_dir = CACHE
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:  # noqa: BLE001
            pass
        dst = cache_dir / "growth_snapshot.db"
        stale = False
        error = ""
        try:
            _copy_growth_db(src, dst)
            copied_at = time.time()
        except Exception as exc:  # noqa: BLE001
            stale = True
            error = "复制失败：%s" % exc
            copied_at = dst.stat().st_mtime if dst.exists() else None
            log("growth copy failed: %s" % exc)

        items = []
        count = None
        if dst.exists():
            try:
                con = sqlite3.connect(str(dst), timeout=1.0)
                try:
                    con.row_factory = sqlite3.Row
                    rows = con.execute(
                        "select ts, text, key, kind, source, created from milestones "
                        "where status = 'active' order by ts desc limit 60"
                    ).fetchall()
                    total = con.execute(
                        "select count(*) from milestones where status = 'active'"
                    ).fetchone()[0]
                    count = int(total)
                    for row in rows:
                        ts = num(row["ts"]) or 0
                        kind = text(row["kind"]) or "first"
                        items.append({
                            "ts": ts,
                            "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                            "date_short": datetime.fromtimestamp(ts).strftime("%m.%d"),
                            "year": datetime.fromtimestamp(ts).strftime("%Y"),
                            "text": text(row["text"]),
                            "kind": kind,
                            "kind_label": KIND_LABELS.get(kind, kind),
                            "source": text(row["source"]),
                        })
                finally:
                    con.close()
            except Exception as exc:  # noqa: BLE001
                stale = True
                error = "读副本失败：%s" % exc
                log("growth read failed: %s" % exc)

        items.sort(key=lambda item: item["ts"])  # 时间轴从左到右
        payload = {
            "available": count is not None,
            "count": count,
            "items": items,
            "stale": stale,
            "error": error,
            "copied_at": copied_at,
            "copied_text": fmt_age(max(0.0, now - copied_at)) if copied_at else "",
        }
        _GROWTH_CACHE.update({"ts": now, "payload": payload})
        return payload


def growth_summary(now):
    payload = build_growth(now)
    latest = payload["items"][-1] if payload.get("items") else None
    return {
        "available": payload.get("available", False),
        "count": payload.get("count"),
        "latest": latest,
    }


# ---- 记忆（只读导出；管理只写队列） ----------------------------------------
_MEMORY_LOCK = threading.Lock()
_MEMORY_CACHE = {"mtime": None, "payload": None}
MEMORY_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
MEMORY_OPS = ("delete", "pin", "edit", "tag")


def _parse_iso(value):
    raw = str(value or "").strip()
    if not raw:
        return 0.0
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw).timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


def _memory_item(raw, recall_map):
    refs = raw.get("refs") if isinstance(raw.get("refs"), dict) else {}
    atom_id = raw.get("id")
    created = str(raw.get("created_at") or "")
    created_ts = _parse_iso(created)
    source_at = str(refs.get("source_time_end") or refs.get("source_time_start") or "")
    source_ts = _parse_iso(source_at)
    event_at = str(raw.get("event_at") or "")
    event_date = str(raw.get("event_date") or "")
    event_precision = str(raw.get("event_precision") or "")
    event_ts = _parse_iso(event_at)
    if event_ts <= 0 and event_date:
        event_ts = _parse_iso(event_date + "T00:00:00+08:00")

    if source_ts > 0:
        display_at = source_at
        sort_ts = source_ts
        time_source = "conversation"
    elif event_ts > 0:
        display_at = event_at or event_date
        sort_ts = event_ts
        time_source = "event"
    else:
        display_at = created
        sort_ts = created_ts
        time_source = "created"
    display_date = display_at[:10]
    display_time = display_at[11:16] if len(display_at) >= 16 else ""
    if not event_precision:
        event_precision = "datetime" if event_at else "unknown"
    event_plausible = bool(
        event_ts > 0 and source_ts > 0 and abs(event_ts - source_ts) <= 86400
    )
    tags = []
    for tag in raw.get("tags") or []:
        tag = str(tag).strip()
        if tag:
            tags.append(tag[:40])
    return {
        "id": atom_id,
        "text": str(raw.get("text") or ""),
        "created_at": created,
        "created_date": created[:10],
        "created_time": created[11:16] if len(created) >= 16 else "",
        "source_at": source_at,
        "event_at": event_at,
        "event_date": event_date or display_date,
        "event_precision": event_precision,
        "event_plausible": event_plausible,
        "time_source": time_source,
        "ts": sort_ts,
        "date": display_date,
        "time": display_time,
        "kind": str(raw.get("kind") or "其他"),
        "tags": tags,
        "pinned": bool(refs.get("pinned")),
        "recall": int(recall_map.get(str(atom_id), 0) or 0),
    }


def build_memory(now, force=False):
    """读 data/exports/memory_export.json（记忆管理每 10 分钟重出）。"""
    path = DATA / "exports" / "memory_export.json"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {
            "available": False, "generated_at": None, "source": "",
            "stats": {}, "items": [], "error": "memory_export.json 还没有",
        }

    with _MEMORY_LOCK:
        cached = _MEMORY_CACHE["payload"]
        if not force and cached and _MEMORY_CACHE["mtime"] == mtime:
            return cached
        try:
            with path.open("r", encoding="utf-8-sig") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("export is not an object")
            raw_items = data.get("items")
            if not isinstance(raw_items, list):
                raise ValueError("items is not a list")
            stats = data.get("stats") if isinstance(data.get("stats"), dict) else {}
            recall_map = {}
            for row in stats.get("top_recalled") or []:
                if isinstance(row, dict):
                    recall_map[str(row.get("id"))] = row.get("count") or 0
            items = [_memory_item(raw, recall_map) for raw in raw_items if isinstance(raw, dict)]
            items.sort(key=lambda item: item["ts"], reverse=True)
            payload = {
                "available": True,
                "generated_at": data.get("generated_at"),
                "source": data.get("source") or "",
                "stats": {
                    "total": stats.get("total", len(items)),
                    "daily": stats.get("daily") or {},
                    "by_kind": stats.get("by_kind") or {},
                    "top_recalled": stats.get("top_recalled") or [],
                    "recalled_at": stats.get("recalled_at") or "",
                },
                "items": items,
                "error": "",
            }
        except Exception as exc:  # noqa: BLE001
            log("read memory export failed: %s" % exc)
            return {
                "available": False, "generated_at": None, "source": "",
                "stats": {}, "items": [], "error": "导出读不了：%s" % exc,
            }
        _MEMORY_CACHE.update({"mtime": mtime, "payload": payload})
        return payload


def build_memory_stats(now):
    payload = build_memory(now)
    return {
        "available": payload.get("available", False),
        "generated_at": payload.get("generated_at"),
        "stats": payload.get("stats", {}),
        "total": len(payload.get("items") or []),
        "error": payload.get("error", ""),
    }


def _memory_target(value, items):
    try:
        target = int(value)
    except (TypeError, ValueError):
        return None
    ids = {str(item.get("id")) for item in items}
    return target if str(target) in ids else None


def write_memory_command(body, now):
    """校验后只写 data/memory_commands/<id>.json；不碰数据库。"""
    if not isinstance(body, dict):
        return None, "body must be an object"
    op = str(body.get("op") or "")
    if op not in MEMORY_OPS:
        return None, "unknown op"
    payload = body.get("payload")
    payload = payload if isinstance(payload, dict) else {}

    memory = build_memory(now)
    if not memory.get("available"):
        return None, "memory export 不可用"
    target = _memory_target(body.get("target"), memory["items"])
    if target is None:
        return None, "target 不在导出里"

    if op == "delete":
        if str(body.get("confirm") or "") != str(target):
            return None, "删除要二次确认（confirm 必须等于 target）"
        payload = {}
    elif op == "pin":
        payload = {"pinned": bool(payload.get("pinned", True))}
    elif op == "edit":
        text = str(payload.get("text") or "").strip()
        if not text:
            return None, "edit 没有正文"
        payload = {"text": text[:4000]}
    elif op == "tag":
        raw = payload.get("tags", payload.get("tag", []))
        if isinstance(raw, str):
            raw = [part for part in re.split(r"[,，、\s]+", raw) if part]
        if not isinstance(raw, list):
            return None, "tags 必须是列表"
        tags = []
        for tag in raw[:10]:
            tag = str(tag).strip()[:24]
            if tag and tag not in tags:
                tags.append(tag)
        payload = {"tags": tags}

    commands = DATA / "memory_commands"
    try:
        commands.mkdir(parents=True, exist_ok=True)
        cmd_id = "panel-%d-%s" % (int(now), uuid.uuid4().hex[:8])
        command = {
            "id": cmd_id,
            "op": op,
            "target": target,
            "payload": payload,
            "at": int(now),
        }
        tmp = commands / (cmd_id + ".tmp")
        tmp.write_text(json.dumps(command, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(str(tmp), str(commands / (cmd_id + ".json")))
        log("memory command %s %s -> %s" % (cmd_id, op, target))
        return command, ""
    except Exception as exc:  # noqa: BLE001
        log("write memory command failed: %s" % exc)
        return None, "写队列失败：%s" % exc


def read_memory_result(cmd_id):
    if not MEMORY_ID_RE.match(cmd_id or ""):
        return None
    path = DATA / "memory_results" / (cmd_id + ".json")
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return {
            "id": cmd_id,
            "status": str(data.get("status") or ""),
            "reason": str(data.get("reason") or ""),
        }
    except FileNotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001
        log("read memory result %s failed: %s" % (cmd_id, exc))
        return None


# ---- 隔离模拟（插件自带 sim/sim_her.py，只用示例数据） --------------------
SIM_SCRIPT = ROOT / "sim" / "sim_her.py"
SIM_PYTHON = Path(sys.executable)
SIM_TIMEOUT = 180
SIM_SCENARIOS = ("full", "weather_matrix", "outing_day", "custom_outing")
SIM_CAMERA_ALLOWED = ("full", "weather_matrix", "outing_day", "custom_outing")
SIM_PLACES = ("demo_mall", "demo_park")
SIM_WEATHERS = ("hot", "warm", "cool", "rain", "snow")
SIM_SCENES = ("中庭", "走廊", "影院里", "休息区", "长椅")
SIM_CUSTOM_TEXT = (
    ("place_name", "自定义地点", 40),
    ("address", "自定义地址", 80),
    ("district", "示例区", 20),
    ("station", "自定义站", 30),
    ("line", "9号线", 20),
    ("location", "121.400000,31.200000", 40),
    ("weather_text", "多云", 30),
    ("scene_name", "中庭", 20),
)
SIM_CUSTOM_KEYS = tuple(row[0] for row in SIM_CUSTOM_TEXT) + ("route_minutes", "fare", "seed")
SIM_PARAM_KEYS = ("place", "weather", "mood", "pain", "energy", "scene") + SIM_CUSTOM_KEYS

_SIM_LOCK = threading.Lock()
_SIM = {
    "id": None,
    "status": "idle",
    "proc": None,
    "started": 0.0,
    "ended": 0.0,
    "returncode": None,
    "log_path": None,
    "summary": {},
    "error": "",
    "stopped": False,
    "scenario": "full",
    "params": {},
}


def _sim_python():
    try:
        if SIM_PYTHON.exists():
            return str(SIM_PYTHON)
    except OSError:
        pass
    return sys.executable


def _read_tail(path, max_lines=260):
    if not path:
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        return [line.rstrip("\n") for line in lines[-max_lines:]]
    except Exception:  # noqa: BLE001
        return []


def _parse_sim(lines):
    text = "\n".join(lines)
    passes = sum(1 for line in lines if line.startswith("[PASS]"))
    fails = sum(1 for line in lines if line.startswith("[FAIL]"))
    match = re.search(r"RESULT (\d+)/(\d+) PASS", text)
    changed = [line for line in lines if line.strip().startswith("CHANGED ")]
    sim_dir_match = re.search(r"^sim_dir=(.+)$", text, re.M)

    machine = None
    for line in reversed(lines):
        if line.startswith("SUMMARY "):
            try:
                machine = json.loads(line[8:])
            except Exception:  # noqa: BLE001
                machine = None
            break

    if isinstance(machine, dict):
        total = int(machine.get("total") or (passes + fails))
        passed = int(machine.get("pass") if machine.get("pass") is not None else passes)
        failed = max(0, total - passed)
        return {
            "pass": passed,
            "fail": failed,
            "total": total,
            "result": ("RESULT %d/%d PASS" % (passed, total)) if total else "",
            "all_pass": bool(machine.get("all_pass")),
            "has_failure": not bool(machine.get("all_pass")),
            "real_ok": bool(machine.get("sha_ok")),
            "sha_ok": bool(machine.get("sha_ok")),
            "changed": len(machine.get("changed") or []),
            "failed": list(machine.get("failed") or []),
            "elapsed_ms": machine.get("elapsed_ms"),
            "temp_removed": machine.get("temp_removed"),
            "scenario": machine.get("scenario"),
            "data": machine.get("data") or {},
            "sim_dir": sim_dir_match.group(1).strip() if sim_dir_match else "",
        }

    total = passes + fails
    return {
        "pass": passes,
        "fail": fails,
        "total": total,
        "result": match.group(0) if match else "",
        "all_pass": "ALL_PASS" in text,
        "has_failure": "HAS_FAILURE" in text,
        "real_ok": ("REAL_SHA256 (before == after):" in text and not changed),
        "sha_ok": ("REAL_SHA256 (before == after):" in text and not changed),
        "changed": len(changed),
        "failed": [],
        "elapsed_ms": None,
        "temp_removed": None,
        "scenario": None,
        "data": {},
        "sim_dir": sim_dir_match.group(1).strip() if sim_dir_match else "",
    }


def sim_status():
    with _SIM_LOCK:
        state = {
            "id": _SIM["id"],
            "status": _SIM["status"],
            "started": _SIM["started"],
            "ended": _SIM["ended"],
            "returncode": _SIM["returncode"],
            "log_path": _SIM["log_path"],
            "summary": dict(_SIM["summary"] or {}),
            "error": _SIM["error"],
            "scenario": _SIM["scenario"],
            "params": dict(_SIM["params"] or {}),
        }
    raw_lines = _read_tail(state["log_path"]) if state["log_path"] else []
    summary = _parse_sim(raw_lines) if raw_lines else state["summary"]
    lines = [line for line in raw_lines if not line.startswith("SUMMARY ")]
    elapsed = 0.0
    if state["started"]:
        end = state["ended"] or time.time()
        elapsed = max(0.0, end - state["started"])
    if state["status"] == "passed" and summary.get("elapsed_ms"):
        elapsed = float(summary["elapsed_ms"]) / 1000.0
    return {
        "id": state["id"],
        "status": state["status"],
        "started": state["started"],
        "ended": state["ended"],
        "elapsed": round(elapsed, 2),
        "returncode": state["returncode"],
        "lines": lines,
        "summary": summary,
        "error": state["error"],
        "scenario": state["scenario"],
        "params": state["params"],
        "scenarios": list(SIM_SCENARIOS),
        "script": str(SIM_SCRIPT),
        "python": _sim_python(),
        "timeout": SIM_TIMEOUT,
    }


def _sim_wait(proc, log_file, run_id):
    returncode = None
    timed_out = False
    try:
        returncode = proc.wait(timeout=SIM_TIMEOUT)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
        try:
            returncode = proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            returncode = -9
    finally:
        try:
            log_file.close()
        except Exception:  # noqa: BLE001
            pass

    with _SIM_LOCK:
        path = _SIM["log_path"]
        stopped = bool(_SIM.get("stopped"))
    lines = _read_tail(path)
    summary = _parse_sim(lines)
    if timed_out:
        summary["error"] = "超过 %d 秒，已终止" % SIM_TIMEOUT
        status = "failed"
    elif stopped:
        summary["error"] = "已手动停止"
        status = "stopped"
    elif returncode == 0 and summary.get("all_pass"):
        status = "passed"
    else:
        status = "failed"

    with _SIM_LOCK:
        _SIM.update({
            "status": status,
            "ended": time.time(),
            "returncode": returncode,
            "summary": summary,
            "proc": None,
            "error": summary.get("error", ""),
        })
    log("sim %s finished: %s rc=%s" % (run_id, status, returncode))


def _sim_custom_argv(body):
    params = {}
    for key, default, limit in SIM_CUSTOM_TEXT:
        value = body.get(key)
        text = str(value if value is not None else "").strip()
        text = text.replace("\r", " ").replace("\n", " ")
        if not text:
            text = default
        if len(text) > limit:
            return None, None, None, "参数 %s 太长（最多 %d 字）" % (key, limit)
        params[key] = text
    if not re.match(r"^[-+]?\d{1,3}(?:\.\d+)?,\s*[-+]?\d{1,3}(?:\.\d+)?$", params["location"]):
        return None, None, None, "经纬度格式要像 121.4,31.2"
    try:
        route = float(body.get("route_minutes", 18))
        fare = float(body.get("fare", 3))
    except (TypeError, ValueError):
        return None, None, None, "路线/票价不是数字"
    if not math.isfinite(route) or route < 1 or route > 45:
        return None, None, None, "route_minutes 要在 1..45 之间"
    if not math.isfinite(fare) or fare < 0 or fare > 100:
        return None, None, None, "fare 要在 0..100 之间"
    params["route_minutes"] = round(route, 1)
    params["fare"] = round(fare, 2)
    seed = body.get("seed")
    if seed not in (None, ""):
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            return None, None, None, "seed 不是整数"
        if seed < 0 or seed > 2147483647:
            return None, None, None, "seed 要在 0..2147483647 之间"
        params["seed"] = seed
    for key in ("mood", "pain", "energy"):
        value = body.get(key)
        if value in (None, ""):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None, None, None, "参数 %s 不是数字" % key
        if not math.isfinite(number) or number < 0 or number > 1:
            return None, None, None, "参数 %s 要在 0..1 之间" % key
        params[key] = round(number, 3)
    argv = [_sim_python(), str(SIM_SCRIPT), "--scenario", "outing_day", "--json", "--place", "custom"]
    for key in ("place_name", "address", "district", "station", "line", "location", "weather_text"):
        argv.extend(["--" + key.replace("_", "-"), params[key]])
    argv.extend(["--scene", params["scene_name"]])
    argv.extend(["--route-minutes", str(params["route_minutes"]), "--fare", str(params["fare"])])
    if "seed" in params:
        argv.extend(["--seed", str(params["seed"])])
    for key in ("mood", "pain", "energy"):
        if key in params:
            argv.extend(["--" + key, str(params[key])])
    return "custom_outing", params, argv, ""


def _sim_argv(body):
    """把面板参数校验并拼成固定 argv；前端永远不拼命令。"""
    if body is None:
        body = {}
    if not isinstance(body, dict):
        return None, None, None, "body must be an object"
    allowed_keys = {"scenario", "camera"}.union(SIM_PARAM_KEYS)
    extra = set(body) - allowed_keys
    if extra:
        return None, None, None, "不认识的参数：%s" % "、".join(sorted(extra))

    scenario = str(body.get("scenario") or "full")
    if scenario not in SIM_SCENARIOS:
        return None, None, None, "场景不在白名单：%s" % scenario
    raw_camera = body.get("camera")
    camera = raw_camera is True or raw_camera == 1 or str(raw_camera).lower() in ("1", "true", "yes", "on")
    if camera and scenario not in SIM_CAMERA_ALLOWED:
        return None, None, None, "上镜模式只允许 outing_day/custom_outing"
    if scenario == "custom_outing":
        return _sim_custom_argv(body)
    argv = [_sim_python(), str(SIM_SCRIPT), "--scenario", scenario, "--json"]
    params = {}

    for key, allowed in (("place", SIM_PLACES), ("weather", SIM_WEATHERS), ("scene", SIM_SCENES)):
        value = body.get(key)
        if value is None or value == "":
            continue
        value = str(value)
        if value not in allowed:
            return None, None, None, "参数 %s 不在白名单：%s" % (key, value)
        params[key] = value
        argv.extend(["--" + key, value])

    for key in ("mood", "pain", "energy"):
        value = body.get(key)
        if value is None or value == "":
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None, None, None, "参数 %s 不是数字" % key
        if not math.isfinite(number) or number < 0 or number > 1:
            return None, None, None, "参数 %s 要在 0..1 之间" % key
        number = round(number, 3)
        params[key] = number
        argv.extend(["--" + key, str(number)])

    return scenario, params, argv, ""


def start_sim(body=None):
    scenario, params, argv, error = _sim_argv(body)
    if error:
        return None, error
    with _SIM_LOCK:
        if _SIM["status"] in ("running", "stopping"):
            return None, "模拟已在跑"
        if not SIM_SCRIPT.exists():
            return None, "sim/sim_her.py 不存在"
        try:
            SIM_DIR = CACHE / "sim"
            SIM_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # noqa: BLE001
            return None, "建日志目录失败：%s" % exc
        run_id = "sim-%d" % int(time.time())
        log_path = SIM_DIR / (run_id + ".log")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        env.pop("DSH_SIM_FORCE_FAIL", None)
        try:
            log_file = log_path.open("w", encoding="utf-8")
            proc = subprocess.Popen(
                argv,
                cwd=str(ROOT),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
            )
        except Exception as exc:  # noqa: BLE001
            try:
                log_file.close()
            except Exception:  # noqa: BLE001
                pass
            log("start sim failed: %s" % exc)
            return None, "启动失败：%s" % exc
        _SIM.update({
            "id": run_id,
            "status": "running",
            "proc": proc,
            "started": time.time(),
            "ended": 0.0,
            "returncode": None,
            "log_path": log_path,
            "summary": {},
            "error": "",
            "stopped": False,
            "scenario": scenario,
            "params": params,
        })
        thread = threading.Thread(target=_sim_wait, args=(proc, log_file, run_id), daemon=True)
        thread.start()
        log("sim %s started (%s %s)" % (run_id, scenario, params))
        return run_id, ""


def stop_sim():
    with _SIM_LOCK:
        proc = _SIM.get("proc")
        if not proc or _SIM["status"] != "running":
            return False, "模拟没在跑"
        _SIM["stopped"] = True
        _SIM["status"] = "stopping"
    try:
        proc.terminate()
    except Exception as exc:  # noqa: BLE001
        return False, "停止失败：%s" % exc
    return True, ""


# ---- 命令面板（只写 data/ui_commands；执行端 scripts/ui_commands.py） ----
UI_ALLOWED = ("sleep", "wake", "eat", "water", "out", "praise", "quiet")
UI_META = [
    ("sleep", "去睡觉", "切到睡觉 · 480 分钟", "作息"),
    ("wake", "起床", "切到 idle · 30 分钟", "作息"),
    ("eat", "去吃饭", "切到吃饭 · 40 分钟", "作息"),
    ("out", "出门走走", "出门 · 90 分钟", "作息"),
    ("water", "喝点水", "记一笔照顾", "照顾"),
    ("praise", "夸她一句", "心情 +0.05", "照顾"),
    ("quiet", "安静一会儿", "15 分钟不主动", "照顾"),
]
UI_TTL = 600
_UI_LOCK = threading.Lock()
_UI_HISTORY = []
_UI_LAST = 0.0


def _ui_paths():
    base = DATA / "ui_commands"
    return base, base / "done"


def _ui_status_of(item):
    base, done = _ui_paths()
    try:
        with (done / (item["id"] + ".json")).open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return str(data.get("status") or "done"), data.get("handled_at")
    except FileNotFoundError:
        pass
    except Exception:  # noqa: BLE001
        pass
    if (base / (item["id"] + ".json")).exists():
        return "queued", None
    return "missing", None


def _scan_ui_history(limit=30):
    """重启后从 ui_commands / done 里补回最近的面板指令（只读）。"""
    base, done = _ui_paths()
    rows = []
    for folder, default_status in ((base, "queued"), (done, None)):
        try:
            paths = list(folder.glob("panel-*.json"))
        except OSError:
            continue
        for path in paths:
            try:
                with path.open("r", encoding="utf-8-sig") as fh:
                    data = json.load(fh)
                cmd = str(data.get("cmd") or "")
                if cmd not in UI_ALLOWED:
                    continue
                at = int(num(data.get("at")) or 0)
                status = default_status or str(data.get("status") or "done")
                label = next((meta[1] for meta in UI_META if meta[0] == cmd), cmd)
                rows.append({
                    "id": path.stem,
                    "cmd": cmd,
                    "label": label,
                    "at": at,
                    "status": status,
                    "handled_at": data.get("handled_at"),
                })
            except Exception:  # noqa: BLE001
                continue
    rows.sort(key=lambda item: item["at"], reverse=True)
    return rows[:limit]


def write_ui_command(body, now):
    """校验后只写 data/ui_commands/<id>.json。"""
    global _UI_LAST
    if not isinstance(body, dict):
        return None, "body must be an object"
    cmd = str(body.get("cmd") or "").strip()
    if cmd not in UI_ALLOWED:
        return None, "不在白名单：%s" % cmd
    with _UI_LOCK:
        if now - _UI_LAST < 1.5:
            return None, "太快了，等 1 秒再发"
        base, _done = _ui_paths()
        try:
            base.mkdir(parents=True, exist_ok=True)
            cmd_id = "panel-%d-%s" % (int(now), uuid.uuid4().hex[:8])
            payload = {"id": cmd_id, "cmd": cmd, "at": int(now)}
            tmp = base / (cmd_id + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(str(tmp), str(base / (cmd_id + ".json")))
        except Exception as exc:  # noqa: BLE001
            log("write ui command failed: %s" % exc)
            return None, "写队列失败：%s" % exc
        label = next((meta[1] for meta in UI_META if meta[0] == cmd), cmd)
        _UI_HISTORY.insert(0, {
            "id": cmd_id,
            "cmd": cmd,
            "label": label,
            "at": int(now),
            "status": "queued",
            "handled_at": None,
        })
        del _UI_HISTORY[30:]
        _UI_LAST = now
        log("ui command %s -> %s" % (cmd, cmd_id))
        return payload, ""


def ui_command_status(now):
    with _UI_LOCK:
        history = [dict(item) for item in _UI_HISTORY]
    seen = {str(item.get("id")) for item in history}
    for item in _scan_ui_history():
        if str(item["id"]) not in seen:
            history.append(item)
    history.sort(key=lambda item: item.get("at") or 0, reverse=True)
    history = history[:30]
    rendered = []
    for item in history:
        status, handled_at = _ui_status_of(item)
        item["status"] = status
        item["handled_at"] = handled_at
        try:
            item["time"] = datetime.fromtimestamp(item["at"]).strftime("%H:%M:%S")
        except Exception:  # noqa: BLE001
            item["time"] = ""
        rendered.append(item)

    rhythm = read_json("rhythm/state.json", {}) or {}
    activity = rhythm.get("activity") if isinstance(rhythm, dict) else {}
    activity = activity if isinstance(activity, dict) else {}
    mood = read_json("mood.json", {}) or {}
    room = read_json("now.json", {}) or {}
    room_data = room.get("room") if isinstance(room, dict) else {}
    room_data = room_data if isinstance(room_data, dict) else {}
    return {
        "ok": True,
        "allowed": [
            {"cmd": cmd, "label": label, "desc": desc, "group": group}
            for cmd, label, desc, group in UI_META
        ],
        "history": rendered,
        "current": {
            "activity": {
                "id": text(activity.get("id")),
                "label": text(activity.get("label")),
                "started": num(activity.get("started")),
            },
            "mood": num(mood.get("value")),
            "room": text(room_data.get("name")),
        },
        "ttl": UI_TTL,
        "note": "只写 data/ui_commands/；心跳每分钟消费；10 分钟内有效",
        "now": now,
    }


def build_all(now=None):
    now = time.time() if now is None else float(now)
    return {
        "schema": SCHEMA,
        "generated_at": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": now,
        "refresh_seconds": 60,
        "state": build_state(now),
        "emotions": build_emotions(now),
        "growth": build_growth(now),
        "profile": dict(PROFILE),
        "features": dict(FEATURES),
        "meta": {
            "read_only": True,
            "data_dir": str(DATA),
            "host": HOST,
            "port": PORT,
            "sources": [
                "data/rhythm/state.json",
                "data/rhythm/body.json",
                "data/now.json",
                "data/wardrobe.json",
                "data/mood.json",
                "data/reality.json",
                "data/emotion/shadow.jsonl",
                "data/growth/growth.db（只读副本）",
            ],
        },
    }


# ---- HTTP ------------------------------------------------------------------
MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml; charset=utf-8",
    ".png": "image/png",
}

STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/style.css": "style.css",
    "/app.js": "app.js",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "BrainPanel/1.0"
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        try:
            path = urlsplit(self.path).path
            if path in STATIC_FILES:
                self._serve_static(STATIC_FILES[path])
                return
            if path == "/api/all":
                self._serve_json(build_all())
                return
            if path == "/api/state":
                self._serve_json(build_state(time.time()))
                return
            if path == "/api/emotions":
                self._serve_json(build_emotions(time.time()))
                return
            if path == "/api/growth":
                self._serve_json(build_growth(time.time(), force=True))
                return
            if path == "/api/memory":
                self._serve_json(build_memory(time.time()))
                return
            if path == "/api/memory/stats":
                self._serve_json(build_memory_stats(time.time()))
                return
            if path.startswith("/api/memory/result/"):
                cmd_id = path.rsplit("/", 1)[-1]
                result = read_memory_result(cmd_id)
                if result is None:
                    if not MEMORY_ID_RE.match(cmd_id or ""):
                        self._serve_json({"ok": False, "error": "bad id"}, status=400)
                    else:
                        self._serve_json({"id": cmd_id, "status": "pending", "reason": ""})
                    return
                self._serve_json({"ok": True, "result": result})
                return
            if path.startswith("/api/sim/") and not FEATURES.get("sim"):
                self._serve_json({"ok": False, "error": "sim disabled"}, status=403)
                return
            if path == "/api/sim/status":
                self._serve_json(sim_status())
                return
            if path == "/api/cmd/status":
                self._serve_json(ui_command_status(time.time()))
                return
            if path == "/api/healthz":
                self._serve_json({"ok": True, "epoch": time.time()})
                return
            if path == "/api/selfcheck":
                self._serve_json({
                    "ok": True,
                    "read_only": True,
                    "host": HOST,
                    "port": PORT,
                    "data_dir": str(DATA),
                    "python": sys.version.split()[0],
                    "growth_db": (DATA / "growth" / "growth.db").exists(),
                    "emotion_log": (DATA / "emotion" / "shadow.jsonl").exists(),
                    "memory_export": (DATA / "exports" / "memory_export.json").exists(),
                    "memory_commands": (DATA / "memory_commands").exists(),
                    "sim_script": SIM_SCRIPT.exists(),
                    "sim_python": _sim_python(),
                    "ui_commands": (DATA / "ui_commands").exists(),
                    "livingmemory_touched": False,
                })
                return
            if path == "/favicon.ico":
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._serve_json({"ok": False, "error": "not found"}, status=404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # noqa: BLE001 - 面板异常自己吞
            log("handler failed: %s\n%s" % (exc, traceback.format_exc()))
            try:
                self._serve_json({"ok": False, "error": "internal error"}, status=500)
            except Exception:  # noqa: BLE001
                pass

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
        try:
            path = urlsplit(self.path).path
            if self.headers.get("X-Panel") != "1":
                self._serve_json({"ok": False, "error": "missing X-Panel"}, status=403)
                return
            origin = self.headers.get("Origin") or ""
            if origin and not re.match(r"^http://(127\.0\.0\.1|localhost):\d+$", origin):
                self._serve_json({"ok": False, "error": "bad origin"}, status=403)
                return

            if path.startswith("/api/sim/") and not FEATURES.get("sim"):
                self._serve_json({"ok": False, "error": "sim disabled"}, status=403)
                return
            if path == "/api/cmd" and not FEATURES.get("commands"):
                self._serve_json({"ok": False, "error": "commands disabled"}, status=403)
                return
            if path == "/api/memory/command" and not FEATURES.get("memory_edit"):
                self._serve_json({"ok": False, "error": "memory edit disabled"}, status=403)
                return

            if path == "/api/sim/run":
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    length = 0
                body = {}
                if length > 0:
                    if length > 8192:
                        self._serve_json({"ok": False, "error": "body too large"}, status=400)
                        return
                    raw = self.rfile.read(length)
                    try:
                        body = json.loads(raw.decode("utf-8"))
                    except Exception:  # noqa: BLE001
                        self._serve_json({"ok": False, "error": "bad json"}, status=400)
                        return
                run_id, error = start_sim(body)
                if error:
                    status = 409 if error == "模拟已在跑" else 400
                    self._serve_json({"ok": False, "error": error}, status=status)
                    return
                self._serve_json({"ok": True, "id": run_id})
                return
            if path == "/api/sim/stop":
                ok, error = stop_sim()
                if not ok:
                    self._serve_json({"ok": False, "error": error}, status=409)
                    return
                self._serve_json({"ok": True})
                return

            if path == "/api/cmd":
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    length = 0
                if length <= 0 or length > 4096:
                    self._serve_json({"ok": False, "error": "bad length"}, status=400)
                    return
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw.decode("utf-8"))
                except Exception:  # noqa: BLE001
                    self._serve_json({"ok": False, "error": "bad json"}, status=400)
                    return
                command, error = write_ui_command(body, time.time())
                if error:
                    self._serve_json({"ok": False, "error": error}, status=400)
                    return
                self._serve_json({"ok": True, "command": command})
                return

            if path != "/api/memory/command":
                self._serve_json({"ok": False, "error": "not found"}, status=404)
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > 64 * 1024:
                self._serve_json({"ok": False, "error": "bad length"}, status=400)
                return
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001
                self._serve_json({"ok": False, "error": "bad json"}, status=400)
                return
            command, error = write_memory_command(body, time.time())
            if error:
                self._serve_json({"ok": False, "error": error}, status=400)
                return
            self._serve_json({"ok": True, "id": command["id"], "command": command})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # noqa: BLE001
            log("post failed: %s\n%s" % (exc, traceback.format_exc()))
            try:
                self._serve_json({"ok": False, "error": "internal error"}, status=500)
            except Exception:  # noqa: BLE001
                pass

    def _send(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _serve_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(body, "application/json; charset=utf-8", status)

    def _serve_static(self, name):
        path = STATIC / name
        try:
            if name == "index.html":
                raw = path.read_text(encoding="utf-8")
                try:
                    boot = json.dumps(build_all(), ensure_ascii=False).replace("</", "<\\/")
                except Exception as exc:  # noqa: BLE001 - 首屏数据失败就让前端自己拉
                    log("boot data failed: %s" % exc)
                    boot = "null"
                raw = raw.replace("/*__BOOT_DATA__*/ null", boot)
                self._send(raw.encode("utf-8"), MIME[".html"])
                return
            body = path.read_bytes()
        except OSError:
            self._serve_json({"ok": False, "error": "missing static"}, status=404)
            return
        self._send(body, MIME.get(path.suffix, "application/octet-stream"))

    def log_message(self, fmt, *args):
        # 不往控制台刷；只写文件，且不记录查询串以外的敏感信息
        log("%s %s" % (self.address_string(), fmt % args))


def run(port=PORT, data_dir=None, host=HOST, runtime_dir=None, profile_path=None):
    global HOST
    HOST = host or "127.0.0.1"
    if data_dir:
        _set_data_dir(data_dir, runtime_dir=runtime_dir, profile_path=profile_path)
    srv = ThreadingHTTPServer((HOST, port), Handler)
    srv.daemon_threads = True
    log("panel start on http://%s:%d  data=%s runtime=%s" % (HOST, port, DATA, CACHE.parent))
    print("%s  http://%s:%d   （只读，Ctrl+C 结束）" % (PROFILE.get("title", "予其真实"), HOST, port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        log("panel stop")


def main(argv=None):
    parser = argparse.ArgumentParser(description="予其真实 · 只读可视化面板")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--data-dir", default=os.environ.get("COMPANION_DATA_DIR", ""), help="状态数据目录（默认 env COMPANION_DATA_DIR 或包内 data）")
    parser.add_argument("--runtime-dir", default=os.environ.get("COMPANION_RUNTIME_DIR", ""), help="缓存/日志目录；默认状态目录")
    parser.add_argument("--profile", default=os.environ.get("COMPANION_PROFILE", ""), help="panel_profile.json 路径")
    parser.add_argument("--check", action="store_true", help="构建一次数据并打印摘要")
    args = parser.parse_args(argv)

    state_dir = args.data_dir or str(DATA)
    _set_data_dir(state_dir, runtime_dir=args.runtime_dir or None, profile_path=args.profile or None)

    if args.check:
        payload = build_all()
        memory = build_memory(time.time())
        summary = {
            "ok": True,
            "her_name": payload.get("profile", {}).get("her_name"),
            "activity": payload["state"]["activity"]["label"],
            "room": payload["state"]["room"]["name"],
            "emotions": {item["name"]: item["current"]["percent"] for item in payload["emotions"]["emotions"]},
            "events": len(payload["emotions"]["events"]),
            "growth_count": payload["growth"]["count"],
            "memory_count": memory.get("stats", {}).get("total"),
            "features": payload.get("features"),
            "read_only": True,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.port < 1 or args.port > 65535:
        print("端口不合法", file=sys.stderr)
        return 2
    run(
        port=args.port,
        data_dir=state_dir,
        host=args.host,
        runtime_dir=args.runtime_dir or None,
        profile_path=args.profile or None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
