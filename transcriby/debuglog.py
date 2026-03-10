#!/usr/bin/env python3
"""Lightweight debug logging with runtime on/off switch."""

from __future__ import annotations

import datetime as dt
import os
import threading

_DEBUG_ENABLED = False
_DEBUG_LOG_PATH = None
_LOCK = threading.Lock()


def get_default_debug_log_path() -> str:
    """Default debug log path: current working directory."""
    return os.path.join(os.getcwd(), "transcriby-debug.log")


def is_debug_logging_enabled() -> bool:
    return bool(_DEBUG_ENABLED)


def set_debug_logging_enabled(enabled: bool, log_path: str | None = None):
    """Enable/disable debug logging and set output file path."""
    global _DEBUG_ENABLED, _DEBUG_LOG_PATH
    _DEBUG_ENABLED = bool(enabled)
    if log_path:
        _DEBUG_LOG_PATH = os.path.abspath(str(log_path))
    else:
        _DEBUG_LOG_PATH = get_default_debug_log_path()


def debug_log(component: str, event: str, message: str = "", **fields):
    """Write a single debug line when logging is enabled."""
    if not _DEBUG_ENABLED:
        return

    target = _DEBUG_LOG_PATH or get_default_debug_log_path()
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"{stamp} [{component}] {event}"
    if message:
        line += f" - {message}"
    if fields:
        ordered = [f"{key}={fields[key]}" for key in sorted(fields)]
        line += " | " + " ".join(ordered)

    try:
        with _LOCK:
            with open(target, mode="a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception:
        # Logging must never break app flow.
        pass
