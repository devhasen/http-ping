"""Structured JSON logger, stdlib only.

Every line is one JSON object: ts, level, logger, msg, plus caller fields.
PII redaction per analytics-spec §8: email/url/api_key/password/token values
are hashed or dropped before emission; free-text URLs truncated to host.
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from typing import Any

REDACT_KEYS = {"email", "password", "api_key", "apikey", "token", "secret", "authorization", "target", "url"}
_lock = threading.Lock()


def _hash(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()[:16]


def _host_only(v: str) -> str:
    host = v.split("://", 1)[-1].split("/", 1)[0].split("?", 1)[0]
    return host[:120]


def sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in REDACT_KEYS and v is not None:
                if lk == "url" and isinstance(v, str):
                    out[k] = {"url_hash": _hash(v), "url_host": _host_only(v)}
                elif isinstance(v, str):
                    out[k] = _hash(v)
                else:
                    out[k] = "[REDACTED]"
            else:
                out[k] = sanitize(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [sanitize(x) for x in obj]
    if isinstance(obj, str) and ("@" in obj and " " not in obj):
        return _hash(obj)
    return obj


class JsonLogger:
    def __init__(self, name: str = "app", stream=None, level: str = "INFO") -> None:
        self.name = name
        self.stream = stream or sys.stdout
        self.level = level.upper()

    def log(self, level: str, msg: str, **fields: Any) -> None:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": level.upper(),
            "logger": self.name,
            "msg": msg,
            **sanitize(fields),
        }
        line = json.dumps(record, separators=(",", ":"), default=str)
        with _lock:
            self.stream.write(line + "\n")

    def info(self, msg: str, **f: Any) -> None: self.log("INFO", msg, **f)
    def warning(self, msg: str, **f: Any) -> None: self.log("WARNING", msg, **f)
    def error(self, msg: str, **f: Any) -> None: self.log("ERROR", msg, **f)
    def debug(self, msg: str, **f: Any) -> None: self.log("DEBUG", msg, **f)


def get_logger(name: str = "app") -> JsonLogger:
    return JsonLogger(name)
