from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DumpEvent:
    prev_stable_lbs: float
    new_stable_lbs: float
    processed_lbs: float


@dataclass
class DumpDetector:
    """Detect a dump event as a sharp drop between two stable plateaus."""

    drop_threshold_lbs: float = 25.0
    min_prev_stable_lbs: float = 10.0

    _prev_stable_lbs: Optional[float] = None
    _awaiting_new_plateau: bool = False

    def update(self, weight_lbs: float, stable: bool) -> Optional[DumpEvent]:
        weight_lbs = float(weight_lbs)
        if not stable:
            return None

        if self._prev_stable_lbs is None:
            self._prev_stable_lbs = weight_lbs
            return None

        prev = float(self._prev_stable_lbs)
        drop = prev - weight_lbs

        # When stable, detect a sufficiently large drop and emit event.
        if prev >= float(self.min_prev_stable_lbs) and drop >= float(self.drop_threshold_lbs):
            evt = DumpEvent(prev_stable_lbs=prev, new_stable_lbs=weight_lbs, processed_lbs=drop)
            self._prev_stable_lbs = weight_lbs
            return evt

        # Otherwise update the reference slowly by snapping to latest stable.
        self._prev_stable_lbs = weight_lbs
        return None


