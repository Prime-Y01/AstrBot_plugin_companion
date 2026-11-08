# -*- coding: utf-8 -*-
"""Lightweight file store for the plugin data directory."""
from __future__ import annotations

import json
import os
from pathlib import Path


class Store:
    def __init__(self, data_dir):
        self.data = Path(data_dir).resolve()
        self.data.mkdir(parents=True, exist_ok=True)

    def path(self, rel):
        return self.data / rel

    def exists(self, rel):
        return self.path(rel).exists()

    def read(self, rel, default=None):
        try:
            with self.path(rel).open("r", encoding="utf-8-sig") as fh:
                return json.load(fh)
        except FileNotFoundError:
            return default
        except Exception:
            return default

    def write(self, rel, data):
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(str(tmp), str(path))

    def write_if_missing(self, rel, data):
        if not self.exists(rel):
            self.write(rel, data)

    def append_jsonl(self, rel, row):
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
