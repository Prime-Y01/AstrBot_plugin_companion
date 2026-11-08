# -*- coding: utf-8 -*-
"""Background heartbeat: time transitions + command consumption."""
from __future__ import annotations

import threading
import time

from .commands import consume
from .store import Store
from .tick import tick


def run(store: Store, interval=60, stop_event=None, on_error=None, lock=None):
    stop_event = stop_event or threading.Event()
    interval = max(5, int(interval))
    while not stop_event.is_set():
        try:
            if lock is not None:
                with lock:
                    tick(store)
                    consume(store)
            else:
                tick(store)
                consume(store)
        except Exception as exc:  # noqa: BLE001
            if on_error:
                try:
                    on_error(exc)
                except Exception:
                    pass
        stop_event.wait(interval)


def start(store: Store, interval=60, on_error=None, lock=None):
    stop_event = threading.Event()
    thread = threading.Thread(
        target=run,
        args=(store, interval, stop_event, on_error, lock),
        name="companion-heartbeat",
        daemon=True,
    )
    thread.start()
    return thread, stop_event
