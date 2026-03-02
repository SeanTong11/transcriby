#!/usr/bin/env python3

import json
from datetime import datetime, timezone

TBY_SCHEMA_VERSION = 1


def build_tby_payload(session_data):
    payload = dict(session_data) if isinstance(session_data, dict) else {}
    payload["schema_version"] = TBY_SCHEMA_VERSION
    payload["exported_at"] = datetime.now(timezone.utc).isoformat()
    return payload


def save_tby(path, session_data):
    payload = build_tby_payload(session_data)
    with open(path, mode="w", encoding="utf-8") as outfile:
        json.dump(payload, outfile, ensure_ascii=False, indent=2)


def load_tby(path):
    with open(path, mode="r", encoding="utf-8") as infile:
        data = json.load(infile)

    if not isinstance(data, dict):
        raise ValueError("Invalid TBY file: top-level JSON value must be an object")

    return data
