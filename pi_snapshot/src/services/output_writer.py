"""Output writer for proportional analog output.

Maps weight (lbs) to 0-10V or 4-20mA using:
- PLC profile curve (primary: trained calibration points)
- Hard-coded 25 lb/V fallback (only when no profile exists)
- optional deadband
- optional ramp limiting

The PLC profile curve is the intended mapping mode.  Operators train it by
capturing known weight/voltage pairs.  The linear fallback (250 lb = 10V,
i.e. 25 lb/V) exists only so the output is not stuck at zero before any
training points have been captured.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class OutputCommand:
    value: float
    units: str  # "V" or "mA"


class PlcProfileLike(Protocol):
    def analog_from_weight(self, weight_lb: float) -> float:
        """Return analog output (V or mA) for the provided weight."""


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(x)))


class OutputWriter:
    """Compute analog output from weight using simple linear mapping."""

    def __init__(self) -> None:
        self._last_weight: Optional[float] = None
        self._last_output: Optional[float] = None
        self._last_units: Optional[str] = None

    def prime_output(self, value: float, units: str) -> None:
        """Seed the internal output state after external/manual commands."""
        self._last_weight = None
        self._last_output = float(value)
        self._last_units = str(units)

    # Hard-coded fallback range: 0-250 lb (fleet standard 25 lb/V).
    # Only used when no PLC profile training points exist.
    _FALLBACK_MIN_LB = 0.0
    _FALLBACK_MAX_LB = 250.0

    def compute(
        self,
        weight_lb: float,
        output_mode: str,
        plc_profile: Optional[PlcProfileLike] = None,
        fault: bool = False,
        armed: bool = True,
        safe_v: float = 0.0,
        safe_ma: float = 4.0,
        deadband_lb: float = 0.5,
        deadband_enabled: bool = True,
        ramp_enabled: bool = False,
        ramp_rate_v: float = 5.0,
        ramp_rate_ma: float = 8.0,
        dt_s: Optional[float] = None,
    ) -> OutputCommand:
        """Map weight to analog output.

        Primary path: PLC profile curve (trained calibration points).
        Fallback: hard-coded linear 0-250 lb → 0-10V (25 lb/V).

        Args:
            weight_lb: Current net weight in pounds.
            output_mode: "0_10V" or "4_20mA".
            plc_profile: Piecewise curve mapping weight to analog output.
            fault: If True, output safe value.
            armed: If False, output safe value (outputs disarmed).
            safe_v: Safe voltage on fault/disarm.
            safe_ma: Safe milliamps on fault/disarm.
            deadband_lb: Minimum weight change to update output.
            deadband_enabled: If False, deadband is bypassed.
            ramp_enabled: If True, limit how fast output can change.
            ramp_rate_v: Max slope in V/s when in 0-10V mode.
            ramp_rate_ma: Max slope in mA/s when in 4-20mA mode.
            dt_s: Loop period in seconds, required for ramp limiting.

        Returns:
            OutputCommand with value and units.
        """
        is_ma = (output_mode == "4_20mA")
        units = "mA" if is_ma else "V"
        lo = 4.0 if is_ma else 0.0
        hi = 20.0 if is_ma else 10.0

        # Fault or disarmed -> safe output
        if fault or not armed:
            self._last_weight = None
            safe_val = float(safe_ma) if is_ma else float(safe_v)
            safe_val = _clamp(safe_val, lo, hi)
            self._last_output = safe_val
            self._last_units = units
            return OutputCommand(value=safe_val, units=units)

        # Deadband: hold last output if change is smaller than threshold
        w = float(weight_lb)
        if (
            deadband_enabled
            and deadband_lb > 0.0
            and self._last_weight is not None
            and abs(w - self._last_weight) < deadband_lb
        ):
            w = self._last_weight
        else:
            self._last_weight = w

        def _linear_fallback(weight: float) -> float:
            """Hard-coded linear fallback: 0-250 lb → 0-10V (25 lb/V).

            Only used when no PLC profile training points exist.
            """
            span = self._FALLBACK_MAX_LB - self._FALLBACK_MIN_LB  # 250.0
            pct = (weight - self._FALLBACK_MIN_LB) / span
            if is_ma:
                return 4.0 + pct * 16.0
            return pct * 10.0

        target: float
        if plc_profile is not None:
            try:
                target = float(plc_profile.analog_from_weight(w))
            except Exception:
                # If profile evaluation fails, fall back to hard-coded linear.
                target = _linear_fallback(w)
        else:
            target = _linear_fallback(w)
        rate = float(ramp_rate_ma) if is_ma else float(ramp_rate_v)

        # Optional ramp limiting to prevent steep output steps.
        if (
            ramp_enabled
            and dt_s is not None
            and dt_s > 0.0
            and self._last_output is not None
            and self._last_units == units
        ):
            max_step = max(0.0, rate) * float(dt_s)
            target = _clamp(target, self._last_output - max_step, self._last_output + max_step)

        value = _clamp(target, lo, hi)
        self._last_output = value
        self._last_units = units
        return OutputCommand(value=value, units=units)
