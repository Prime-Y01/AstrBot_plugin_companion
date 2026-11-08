# -*- coding: utf-8 -*-
"""Path resolution: config > environment > default.

No drive letters and no absolute paths are baked into the package.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_DATA_DIR = "COMPANION_DATA_DIR"
ENV_RUNTIME_DIR = "COMPANION_RUNTIME_DIR"
ENV_EXTERNAL_DATA_DIR = "COMPANION_EXTERNAL_DATA_DIR"
ENV_PROFILE = "COMPANION_PROFILE"


def resolve_path(value=None, env_name=None, default=None, base=None):
    """Resolve a configured path with the documented precedence."""
    raw = str(value or "").strip()
    if not raw and env_name:
        raw = os.environ.get(env_name, "").strip()
    if not raw:
        if default is None:
            return None
        path = Path(str(default)).expanduser()
    else:
        path = Path(raw).expanduser()
    if not path.is_absolute() and base is not None:
        path = Path(base) / path
    return path.resolve()


def resolve_data_dir(value=None, default=None, base=None):
    return resolve_path(value, ENV_DATA_DIR, default, base)


def resolve_runtime_dir(value=None, default=None, base=None):
    return resolve_path(value, ENV_RUNTIME_DIR, default, base)


def resolve_external_dir(value=None, default=None, base=None):
    return resolve_path(value, ENV_EXTERNAL_DATA_DIR, default, base)
