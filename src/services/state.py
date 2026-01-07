from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class LiveState:
    """Thread-safe shared snapshot for the web UI."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _snap: Dict[str, Any] = field(default_factory=dict, init=False)

    def set(self, **kwargs: Any) -> None:
        with self._lock:
            self._snap.update(kwargs)
            self._snap["last_update_utc"] = _utc_now()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            # shallow copy is enough for scaffold usage
            return dict(self._snap)


