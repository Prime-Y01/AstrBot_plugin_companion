# -*- coding: utf-8 -*-
"""AstrBot plugin: Companion / 予其真实 panel.

Two modes:
- ``source_mode=plugin`` (default): the plugin owns a portable state engine in
  its plugin_data directory; the heartbeat advances it and owner chat updates
  mood/activity/memory/growth.
- ``source_mode=external``: read an existing state directory (for example the
  owner's own bot), start the panel read-only against it, and leave commands to
  that bot's existing heartbeat. No engine/chat writes.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools

from .engine import heartbeat_start, on_message as engine_on_message, seed
from .engine.paths import (
    ENV_DATA_DIR,
    ENV_EXTERNAL_DATA_DIR,
    ENV_RUNTIME_DIR,
    resolve_path,
)
from .engine.store import Store

PLUGIN_NAME = "astrbot_plugin_companion"
PANEL_HOST = "127.0.0.1"


def _free_port(start):
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((PANEL_HOST, port))
                actual = sock.getsockname()[1]
                return actual if actual else port
            except OSError:
                continue
    return None


class CompanionPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.cfg = config or {}
        self.enabled = bool(self.cfg.get("enabled", True))
        default_plugin_dir = Path(str(StarTools.get_data_dir(PLUGIN_NAME)))
        self.plugin_dir = resolve_path(
            self.cfg.get("runtime_dir"),
            ENV_RUNTIME_DIR,
            default_plugin_dir,
            base=default_plugin_dir,
        )
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_state_dir = resolve_path(
            self.cfg.get("data_dir"),
            ENV_DATA_DIR,
            default_plugin_dir,
            base=default_plugin_dir,
        )

        self.profile = {
            "her_name": str(self.cfg.get("her_name") or "她")[:40],
            "owner_name": str(self.cfg.get("owner_name") or "你")[:40],
            "title": str(self.cfg.get("title") or "予其真实")[:40],
            "subtitle": "COMPANION · STATE",
        }
        raw_owner_ids = str(self.cfg.get("owner_ids") or "")
        self.owner_ids = {
            part.strip()
            for part in raw_owner_ids.replace(";", ",").split(",")
            if part.strip()
        }
        self.chat_events = bool(self.cfg.get("chat_events", True))
        self.chat_owner_only = bool(self.cfg.get("chat_owner_only", True))
        self.chat_private_only = bool(self.cfg.get("chat_private_only", True))
        self.chat_memory = bool(self.cfg.get("chat_memory", True))
        self.chat_memory_interval = max(10, int(self.cfg.get("chat_memory_interval") or 120))
        self.chat_growth = bool(self.cfg.get("chat_growth", True))
        self._engine_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._panel = None
        self._panel_log = None
        self.port = int(self.cfg.get("port") or 8765)

        source_mode = str(self.cfg.get("source_mode") or "plugin").strip().lower()
        external_dir = resolve_path(
            self.cfg.get("external_data_dir"),
            ENV_EXTERNAL_DATA_DIR,
            None,
            base=default_plugin_dir,
        )
        self.external = source_mode == "external"
        if self.external:
            if external_dir is None or not external_dir.is_dir():
                logger.warning(
                    "[companion] external_data_dir invalid: %s; fallback to plugin mode",
                    external_dir or "",
                )
                self.external = False
            else:
                self.state_dir = external_dir
        if not self.external:
            self.state_dir = plugin_state_dir

        self.features = {
            "memory": bool(self.cfg.get("memory_enabled", True)),
            "memory_edit": False,
            "sim": False if self.external else (
                bool(self.cfg.get("sim_enabled", True))
                and (Path(__file__).resolve().parent / "sim" / "sim_her.py").is_file()
            ),
            "commands": True,
        }
        self.store = Store(self.state_dir)
        self.plugin_store = Store(self.plugin_dir)

        if self.external:
            self.features["sim"] = False
        else:
            demo = bool(self.cfg.get("demo_mode", True))
            seed(self.state_dir, demo=demo, profile=self.profile, features=self.features)
        self.plugin_store.write("panel_profile.json", {
            "profile": self.profile,
            "features": self.features,
        })

        if not self.enabled:
            logger.info("[companion] disabled by config")
            return
        self._start_panel()
        if not self.external:
            interval = max(10, int(self.cfg.get("heartbeat_seconds") or 60))
            self._thread, self._stop = heartbeat_start(
                self.store,
                interval=interval,
                on_error=lambda exc: logger.warning("[companion] heartbeat: %s", exc),
                lock=self._engine_lock,
            )
        logger.info(
            "[companion] mode=%s state=%s panel=http://%s:%s",
            "external" if self.external else "plugin",
            self.state_dir,
            PANEL_HOST,
            self.port,
        )

    def _start_panel(self):
        panel = Path(__file__).resolve().parent / "panel" / "server.py"
        if not panel.is_file():
            logger.warning("[companion] panel/server.py missing")
            return
        port = _free_port(self.port)
        if port is None:
            logger.warning("[companion] no free port near %s", self.port)
            return
        self.port = port
        try:
            log_path = self.plugin_dir / "panel_logs" / "panel.out"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._panel_log = log_path.open("a", encoding="utf-8")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            self._panel = subprocess.Popen(
                [
                    sys.executable,
                    str(panel),
                    "--data-dir",
                    str(self.state_dir),
                    "--runtime-dir",
                    str(self.plugin_dir),
                    "--profile",
                    str(self.plugin_dir / "panel_profile.json"),
                    "--port",
                    str(self.port),
                ],
                cwd=str(Path(__file__).resolve().parent),
                stdout=self._panel_log,
                stderr=subprocess.STDOUT,
                env=env,
                creationflags=flags,
            )
            time.sleep(0.6)
            if self._panel.poll() is not None:
                logger.warning("[companion] panel exited immediately; see %s", log_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[companion] panel start failed: %s", exc)
            self._panel = None

    def _stop_panel(self):
        panel = self._panel
        self._panel = None
        if panel is not None and panel.poll() is None:
            try:
                panel.terminate()
                panel.wait(timeout=4)
            except Exception:  # noqa: BLE001
                try:
                    panel.kill()
                except Exception:
                    pass
        if self._panel_log is not None:
            try:
                self._panel_log.close()
            except Exception:
                pass
            self._panel_log = None

    @filter.event_message_type(filter.EventMessageType.ALL, priority=999)
    async def on_message(self, event: AstrMessageEvent):
        """Update the portable state from owner chat; never blocks a reply."""
        if self.external or not self.enabled or not self.chat_events:
            return
        try:
            sender = event.get_sender_id() or ""
            if sender and sender == (event.get_self_id() or ""):
                return
            if self.chat_private_only and not event.is_private_chat():
                return
            is_owner = event.is_admin() or (bool(sender) and sender in self.owner_ids)
            if self.chat_owner_only and not is_owner:
                return
            text_value = (event.get_message_str() or "").strip()
            if not text_value or text_value.startswith("/"):
                return
            with self._engine_lock:
                result = engine_on_message(
                    self.store,
                    text_value,
                    is_owner=is_owner,
                    now=time.time(),
                    remember=self.chat_memory,
                    growth=self.chat_growth,
                    memory_interval=self.chat_memory_interval,
                )
            if result.get("memory"):
                logger.debug("[companion] chat memory +1")
        except Exception as exc:  # noqa: BLE001
            logger.warning("[companion] chat bridge: %s", exc)

    @filter.command("面板")
    async def panel_cmd(self, event: AstrMessageEvent):
        """查看予其真实面板地址（仅主人）。"""
        if not event.is_admin():
            yield event.plain_result("面板只给主人看。")
            return
        if self._panel is None or self._panel.poll() is not None:
            yield event.plain_result("面板没起来；看 plugin_data 里的 panel_logs/panel.out。")
            return
        yield event.plain_result(
            "予其真实：http://%s:%s\n只监听本机；命令/记忆/模拟按配置显示。"
            % (PANEL_HOST, self.port)
        )

    @filter.command("状态")
    async def state_cmd(self, event: AstrMessageEvent):
        """查看她此刻的状态（仅主人）。"""
        if not event.is_admin():
            yield event.plain_result("这个只给主人看。")
            return
        state = self.store.read("rhythm/state.json", {}) or {}
        activity = state.get("activity") or {}
        mood = self.store.read("mood.json", {}) or {}
        yield event.plain_result(
            "她此刻：%s\n心情：%s\n模式：%s"
            % (
                activity.get("label") or "——",
                round(float(mood.get("value") or 0.62) * 100),
                "外部只读" if self.external else "插件引擎",
            )
        )

    async def terminate(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        self._stop_panel()
        logger.info("[companion] stopped")
