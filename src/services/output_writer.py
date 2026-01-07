from __future__ import annotations

import math
from dataclasses import dataclass

from src.core.plc_profile import PlcProfileCurve


@dataclass
class OutputCommand:
    value: float
    units: str  # "V" or "mA"


def clamp(x: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(x)))


@dataclass
class OutputWriter:
    """Compute analog output command for a desired weight.

    - Applies clamping to configured min/max weight.
    - Applies optional PLC profile mapping (piecewise linear).
    - Applies optional deadband (weight domain) and ramp/slew limiting (output domain).
    """

    min_lb: float = 0.0
    max_lb: float = 300.0

    # Output control
    deadband_enabled: bool = False
    deadband_lb: float = 0.5
    ramp_enabled: bool = False
    ramp_rate_v: float = 5.0   # V/s
    ramp_rate_ma: float = 8.0  # mA/s

    # Internal state (not persisted)
    _last_weight_for_output: float | None = None
    _last_output_mode: str | None = None
    _last_output_value: float | None = None
    _last_output_units: str | None = None

    def reset_state(self) -> None:
        self._last_weight_for_output = None
        self._last_output_mode = None
        self._last_output_value = None
        self._last_output_units = None

    def seed_output_state(self, *, output_mode: str, value: float, units: str) -> None:
        """Seed the last-output state (used when forcing safe/disarmed outputs)."""
        self._last_output_mode = str(output_mode)
        self._last_output_units = str(units)
        self._last_output_value = float(value)

    def linear_map(self, weight_lb: float, output_mode: str) -> OutputCommand:
        w = clamp(weight_lb, self.min_lb, self.max_lb)
        span = max(1e-9, float(self.max_lb - self.min_lb))
        pct = (w - self.min_lb) / span

        if output_mode == "4_20mA":
            ma = 4.0 + pct * 16.0
            return OutputCommand(value=ma, units="mA")
        # default 0-10V
        v = pct * 10.0
        return OutputCommand(value=v, units="V")

    @staticmethod
    def _clamp_output(cmd: OutputCommand, output_mode: str) -> OutputCommand:
        if output_mode == "4_20mA":
            return OutputCommand(value=clamp(cmd.value, 4.0, 20.0), units="mA")
        return OutputCommand(value=clamp(cmd.value, 0.0, 10.0), units="V")

    def _apply_deadband(self, weight_lb: float) -> float:
        """Return weight to use for output mapping (may hold last value)."""
        w = float(weight_lb)
        if not self.deadband_enabled:
            self._last_weight_for_output = w
            return w
        db = max(0.0, float(self.deadband_lb))
        if self._last_weight_for_output is None:
            self._last_weight_for_output = w
            return w
        if abs(w - float(self._last_weight_for_output)) < db:
            return float(self._last_weight_for_output)
        self._last_weight_for_output = w
        return w

    def _apply_ramp(self, cmd: OutputCommand, *, output_mode: str, dt_s: float | None) -> OutputCommand:
        """Apply slew-rate limiting to the output command."""
        if not self.ramp_enabled:
            self._last_output_mode = str(output_mode)
            self._last_output_units = str(cmd.units)
            self._last_output_value = float(cmd.value)
            return cmd

        if dt_s is None:
            dt = 0.0
        else:
            dt = max(0.0, float(dt_s))

        mode = str(output_mode)
        if self._last_output_value is None or self._last_output_mode != mode or self._last_output_units != str(cmd.units) or dt <= 0.0:
            self._last_output_mode = mode
            self._last_output_units = str(cmd.units)
            self._last_output_value = float(cmd.value)
            return cmd

        rate = float(self.ramp_rate_ma if cmd.units == "mA" else self.ramp_rate_v)
        rate = max(0.0, rate)
        max_step = rate * dt

        prev = float(self._last_output_value)
        target = float(cmd.value)
        delta = target - prev
        if max_step <= 0.0 or abs(delta) <= max_step:
            out = target
        else:
            out = prev + math.copysign(max_step, delta)

        self._last_output_value = float(out)
        return OutputCommand(value=float(out), units=str(cmd.units))

    def apply_output_controls(self, cmd: OutputCommand, *, output_mode: str, dt_s: float | None = None) -> OutputCommand:
        """Apply clamping + ramp control to an already-computed command."""
        cmd = self._clamp_output(cmd, output_mode=str(output_mode))
        return self._apply_ramp(cmd, output_mode=str(output_mode), dt_s=dt_s)

    def compute(
        self,
        weight_lb: float,
        output_mode: str,
        plc_profile: PlcProfileCurve | None = None,
        fault: bool = False,
        safe_v: float = 0.0,
        safe_ma: float = 4.0,
        dt_s: float | None = None,
    ) -> OutputCommand:
        if fault:
            if output_mode == "4_20mA":
                return OutputCommand(value=float(safe_ma), units="mA")
            return OutputCommand(value=float(safe_v), units="V")

        # Apply optional deadband in the weight domain before mapping.
        weight_for_output = self._apply_deadband(float(weight_lb))

        # If we have a PLC mapping curve with enough points, it directly yields analog value.
        if plc_profile is not None and len(plc_profile.points) >= 2:
            analog = plc_profile.analog_for_weight(float(weight_for_output))
            units = "mA" if output_mode == "4_20mA" else "V"
            cmd = OutputCommand(value=float(analog), units=units)
            cmd = self._clamp_output(cmd, output_mode=str(output_mode))
            return self._apply_ramp(cmd, output_mode=str(output_mode), dt_s=dt_s)

        cmd = self.linear_map(weight_lb=float(weight_for_output), output_mode=str(output_mode))
        cmd = self._clamp_output(cmd, output_mode=str(output_mode))
        return self._apply_ramp(cmd, output_mode=str(output_mode), dt_s=dt_s)


