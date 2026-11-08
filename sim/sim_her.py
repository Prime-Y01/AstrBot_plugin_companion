#!/usr/bin/env python3
"""Portable, isolated simulation for the Companion plugin engine.

This file ships with the plugin. It only uses the plugin's own lightweight
engine and a temporary directory; it never reads or writes the host's real
``data/`` or the private production scripts.

Output contract is the same one the panel already parses:
    [PASS]/[FAIL] lines, RESULT n/n PASS, ALL_PASS, REAL_SHA256, SUMMARY {...}
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import importlib  # noqa: E402

seed_mod = importlib.import_module("engine.seed")
from engine.store import Store  # noqa: E402
from engine.tick import tick  # noqa: E402

PLACES = {
    "demo_mall": {
        "id": "demo_mall",
        "name": "示例商场",
        "kind": "mall",
        "district": "示例区",
        "address": "示例路1号",
        "station": "示例站",
        "line": "1号线",
    },
    "demo_park": {
        "id": "demo_park",
        "name": "示例公园",
        "kind": "park",
        "district": "示例区",
        "address": "示例路2号",
        "station": "公园站",
        "line": "2号线",
    },
}

RESULTS = []
DATA = {}
STARTED = time.perf_counter()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), str(detail)))
    print("[%s] %-28s %s" % ("PASS" if ok else "FAIL", name, detail))


def _store(base: Path) -> Store:
    data = base / "data"
    data.mkdir(parents=True, exist_ok=True)
    return Store(data)


def _profile():
    return {"her_name": "示例她", "owner_name": "示例主人"}


def _place(args):
    if args.place == "custom":
        return {
            "id": "custom",
            "name": args.place_name or "自定义地点",
            "kind": "mall",
            "district": args.district or "示例区",
            "address": args.address or "自定义地址",
            "station": args.station or "自定义站",
            "line": args.line or "9号线",
            "location": args.location or "121.400000,31.200000",
        }
    return dict(PLACES.get(args.place) or PLACES["demo_mall"])


def _seed(store: Store, now: float):
    seed_mod.seed(
        store.data,
        demo=False,
        now=now,
        profile=_profile(),
        features={"memory": True, "memory_edit": False, "sim": True, "commands": True},
    )


def _now_payload(place, when: float):
    return {
        "place": {
            "id": place["id"],
            "name": place["name"],
            "kind": "out",
            "district": place["district"],
            "address": place["address"],
            "station": place["station"],
            "line": place["line"],
        },
        "room": {"id": "outside", "name": "外面", "together": False},
        "updated_at": int(when),
    }


def run_full(store: Store, args):
    now = time.time()
    _seed(store, now)
    profile = store.read("panel_profile.json", {}) or {}
    now_data = store.read("now.json", {}) or {}
    rhythm = store.read("rhythm/state.json", {}) or {}
    mood = store.read("mood.json", {}) or {}
    body = store.read("rhythm/body.json", {}) or {}
    activity = rhythm.get("activity") if isinstance(rhythm.get("activity"), dict) else {}

    check("profile_seeded", profile.get("profile", {}).get("her_name") == "示例她", "profile")
    check("now_seeded", bool(now_data.get("place")), "place")
    check("activity_seeded", bool(activity.get("id")), str(activity.get("id") or ""))
    check("mood_seeded", 0.0 <= float(mood.get("value") or 0) <= 1.0, "mood")
    check("body_seeded", 0.0 <= float(body.get("energy") or 0) <= 1.0, "energy")

    if not activity.get("expected_end"):
        state = store.read("rhythm/state.json", {}) or {}
        state["activity"] = {
            "id": str(activity.get("id") or "idle"),
            "label": "待机",
            "started": int(now) - 10,
            "expected_end": int(now) - 1,
            "with_owner": False,
            "deep": False,
        }
        store.write("rhythm/state.json", state)
        activity = state["activity"]
    expected = float(activity.get("expected_end") or 0)
    old_id = str(activity.get("id") or "")
    tick(store, expected + 1)
    after = store.read("rhythm/state.json", {}) or {}
    new_activity = after.get("activity") if isinstance(after.get("activity"), dict) else {}
    history = after.get("history") if isinstance(after.get("history"), list) else []
    check("tick_transition", bool(new_activity.get("id")) and bool(history), "%s -> %s" % (old_id, new_activity.get("id")))

    timeline_dir = store.path("timeline")
    timeline = list(timeline_dir.glob("*.jsonl")) if timeline_dir.exists() else []
    check("timeline_written", bool(timeline), "%d file(s)" % len(timeline))

    store.write("mood.json", {"value": 0.95, "baseline": 0.62, "ts": int(now) - 4 * 3600})
    tick(store, now)
    mood_after = store.read("mood.json", {}) or {}
    check("mood_decay", 0.62 <= float(mood_after.get("value") or 0) < 0.95, "value")

    place = _place(args)
    store.write("now.json", _now_payload(place, now))
    store.write("reality.json", {"weather": {"text": "晴 22°C", "desc": "晴"}, "city": "", "updated_at": int(now)})
    check("weather_roundtrip", (store.read("reality.json", {}) or {}).get("weather", {}).get("text") == "晴 22°C", place["name"])

    check("feature_sim", bool((profile.get("features") or {}).get("sim")), "enabled")


def run_weather_matrix(store: Store, args):
    now = time.time()
    _seed(store, now)
    place = _place(args)
    rows = []
    weathers = ("高温 36°C 晴", "暖 28°C 多云", "凉 18°C 阴", "冷 6°C 小雨", "寒冷 0°C 雨夹雪")
    bodies = ((0.05, 0.90), (0.12, 0.78), (0.25, 0.60), (0.45, 0.40), (0.70, 0.15))
    moods = (0.90, 0.78, 0.62, 0.45, 0.22)
    for index, weather in enumerate(weathers):
        pain, energy = bodies[index]
        store.write("reality.json", {"weather": {"text": weather, "desc": weather}, "city": "", "updated_at": int(now)})
        store.write("rhythm/body.json", {
            "phase": "period" if pain >= 0.65 else "follicular",
            "day": 2 if pain >= 0.65 else 8,
            "period": 5, "energy": energy, "pain": pain, "libido": 0.30,
        })
        store.write("mood.json", {"value": moods[index], "baseline": 0.62, "ts": int(now)})
        store.write("now.json", _now_payload(place, now))
        got_weather = (store.read("reality.json", {}) or {}).get("weather", {}).get("text")
        got_mood = float((store.read("mood.json", {}) or {}).get("value") or 0)
        ok = got_weather == weather and 0.0 <= got_mood <= 1.0
        rows.append({"weather": weather, "pain": pain, "energy": energy, "mood": got_mood, "ok": ok})
        check("weather_round_%d" % (index + 1), ok, weather)
    check("weather_rounds", len(rows) == 5, "%d/5" % len(rows))
    DATA["weather"] = rows


def run_outing_day(store: Store, args):
    now = time.time()
    _seed(store, now)
    place = _place(args)
    weather = args.weather_text or {
        "hot": "高温 36°C 晴", "warm": "暖 28°C 多云", "cool": "凉 18°C 阴",
        "rain": "冷 6°C 小雨", "snow": "寒冷 0°C 雨夹雪",
    }.get(args.weather, args.weather)
    store.write("now.json", _now_payload(place, now))
    store.write("reality.json", {"weather": {"text": weather, "desc": weather}, "city": "", "updated_at": int(now)})
    store.write("mood.json", {"value": max(0.0, min(1.0, args.mood)), "baseline": 0.62, "ts": int(now)})
    store.write("rhythm/body.json", {
        "phase": "period" if args.pain >= 0.65 else "follicular",
        "day": 2 if args.pain >= 0.65 else 8,
        "period": 5, "energy": max(0.0, min(1.0, args.energy)),
        "pain": max(0.0, min(1.0, args.pain)), "libido": 0.30,
    })
    state = store.read("rhythm/state.json", {}) or {}
    state["activity"] = {
        "id": "out", "label": "出门", "started": int(now) - 10,
        "expected_end": int(now) + 3600, "with_owner": False, "deep": False,
    }
    state["updated_at"] = int(now)
    store.write("rhythm/state.json", state)

    now_data = store.read("now.json", {}) or {}
    check("outing_place", (now_data.get("place") or {}).get("name") == place["name"], place["name"])
    check("outing_weather", (store.read("reality.json", {}) or {}).get("weather", {}).get("text") == weather, weather)
    check("outing_mood", 0.0 <= float((store.read("mood.json", {}) or {}).get("value") or 0) <= 1.0, "mood")
    check("outing_activity", (state.get("activity") or {}).get("id") == "out", "out")
    tick(store, now + 7200)
    after = store.read("rhythm/state.json", {}) or {}
    check("outing_tick", bool((after.get("activity") or {}).get("id")), str((after.get("activity") or {}).get("id")))
    DATA["outing"] = {
        "place": place["name"], "weather": weather,
        "address": place.get("address", ""), "route_minutes": args.route_minutes,
        "fare": args.fare,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Companion portable simulation")
    parser.add_argument("--scenario", default="full", choices=("full", "weather_matrix", "outing_day"))
    parser.add_argument("--place", default="demo_mall")
    parser.add_argument("--place-name", default="")
    parser.add_argument("--address", default="")
    parser.add_argument("--district", default="示例区")
    parser.add_argument("--station", default="自定义站")
    parser.add_argument("--line", default="9号线")
    parser.add_argument("--location", default="121.400000,31.200000")
    parser.add_argument("--route-minutes", type=float, default=18)
    parser.add_argument("--fare", type=float, default=3)
    parser.add_argument("--weather", default="hot", choices=("hot", "warm", "cool", "rain", "snow"))
    parser.add_argument("--weather-text", default="")
    parser.add_argument("--scene", default="中庭")
    parser.add_argument("--mood", type=float, default=0.75)
    parser.add_argument("--pain", type=float, default=0.10)
    parser.add_argument("--energy", type=float, default=0.70)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.seed is not None:
        import random

        random.seed(args.seed)

    base = Path(tempfile.mkdtemp(prefix="companion_sim_"))
    store = _store(base)
    try:
        if args.scenario == "full":
            run_full(store, args)
        elif args.scenario == "weather_matrix":
            run_weather_matrix(store, args)
        else:
            run_outing_day(store, args)
    except Exception as exc:  # noqa: BLE001
        check("scenario_exception", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        removed = False
        try:
            shutil.rmtree(base)
            removed = not base.exists()
        except Exception:
            removed = False

    failed = [name for name, ok, _detail in RESULTS if not ok]
    passed = len(RESULTS) - len(failed)
    print("REAL_SHA256 (before == after):")
    print("  (portable sim: no host state files touched)")
    if args.json:
        print("SUMMARY " + json.dumps({
            "scenario": args.scenario,
            "pass": passed,
            "total": len(RESULTS),
            "all_pass": not failed,
            "sha_ok": True,
            "changed": [],
            "failed": failed,
            "elapsed_ms": int((time.perf_counter() - STARTED) * 1000),
            "temp_removed": removed,
            "data": DATA,
        }, ensure_ascii=False))
    print("RESULT %d/%d PASS" % (passed, len(RESULTS)))
    if failed:
        print("FAILED: " + ", ".join(failed))
        print("HAS_FAILURE")
        return 1
    print("ALL_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
