from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DriftStatus:
    warnings: List[dict] = field(default_factory=list)


@dataclass
class DriftDetector:
    """Detect changes in per-channel contribution ratio over time.

    Strategy (scaffold):
    - Maintain a baseline ratio per channel using EMA while stable.
    - If current ratio deviates from baseline by more than threshold for N consecutive stable samples, raise warning.
    """

    ratio_threshold: float = 0.12  # absolute ratio delta (e.g., 0.12 = 12% points)
    ema_alpha: float = 0.02
    consecutive_required: int = 20

    _baseline: Dict[int, float] = field(default_factory=dict)
    _consecutive: Dict[int, int] = field(default_factory=dict)

    def update(self, ratios: Dict[int, float], stable: bool) -> DriftStatus:
        status = DriftStatus()

        if not stable:
            # Do not learn baseline during unstable operation.
            for ch in ratios:
                self._consecutive[ch] = 0
            return status

        for ch, r in ratios.items():
            r = float(r)
            if ch not in self._baseline:
                self._baseline[ch] = r
                self._consecutive[ch] = 0
                continue

            # update baseline slowly
            b = self._baseline[ch]
            b = b + float(self.ema_alpha) * (r - b)
            self._baseline[ch] = b

            delta = abs(r - b)
            if delta > float(self.ratio_threshold):
                self._consecutive[ch] = self._consecutive.get(ch, 0) + 1
            else:
                self._consecutive[ch] = 0

            if self._consecutive[ch] >= int(self.consecutive_required):
                status.warnings.append(
                    {
                        "channel": ch,
                        "baseline_ratio": b,
                        "current_ratio": r,
                        "delta": delta,
                    }
                )

        return status

    def baseline(self) -> Dict[int, float]:
        return dict(self._baseline)


