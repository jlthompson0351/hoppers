from __future__ import annotations

import math
import os
import random
import time
from dataclasses import dataclass
from typing import List

from src.hw.interfaces import Daq24b8vin, HardwareBundle, MegaInd


def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name, "").strip()
    if not v:
        return float(default)
    try:
        return float(v)
    except ValueError:
        return float(default)


def _env_ratios(name: str, default: List[float]) -> List[float]:
    v = os.environ.get(name, "").strip()
    if not v:
        return list(default)
    try:
        parts = [p.strip() for p in v.split(",")]
        vals = [float(p) for p in parts if p]
        return vals if vals else list(default)
    except Exception:  # noqa: BLE001
        return list(default)


@dataclass
class _SimModel:
    # Total weight dynamic (lb)
    base_weight_lbs: float = 120.0
    step_amp_lbs: float = 60.0
    step_period_s: float = 18.0

    # Excitation (V)
    excitation_nom_v: float = 10.0
    excitation_sag_amp_v: float = 0.6
    excitation_period_s: float = 90.0

    # Noise/vibration
    vib_amp_lb: float = 3.0
    vib_hz: float = 8.0
    noise_lb_rms: float = 0.8

    # Channel distribution
    channel_ratios: List[float] = None  # set in __post_init__

    # Load cell scaling assumption (for simulation only)
    # 3 mV/V rated output at full scale; assume 300 lb total corresponds to 30 mV aggregate at 10V.
    mv_per_lb_at_10v: float = 30.0 / 300.0  # 0.1 mV/lb aggregate

    def __post_init__(self) -> None:
        if self.channel_ratios is None:
            self.channel_ratios = [0.25, 0.25, 0.25, 0.25]


class SimulatedDaq(Daq24b8vin):
    def __init__(self, model: _SimModel, average_samples: int = 1) -> None:
        self._m = model
        self._t0 = time.monotonic()
        self._gain_codes = [7] * 8  # default to highest gain / smallest range
        self.average_samples = max(1, int(average_samples))

    def _t(self) -> float:
        return time.monotonic() - self._t0

    def read_differential_mv(self, channel: int) -> float:
        t = self._t()
        if channel < 0 or channel > 7:
            raise ValueError(f"Invalid DAQ channel: {channel}")

        # Slow step-like process
        step = self._m.step_amp_lbs * (0.5 + 0.5 * math.sin(2 * math.pi * t / self._m.step_period_s))
        total_lb = self._m.base_weight_lbs + step

        vib = self._m.vib_amp_lb * math.sin(2 * math.pi * self._m.vib_hz * t)
        noise = random.gauss(0.0, self._m.noise_lb_rms)

        # Apply distribution ratio per channel (channels 0..3 have signal by default, others near zero)
        ratios = self._m.channel_ratios
        ratio = ratios[channel] if channel < len(ratios) else 0.0

        def _one_sample() -> float:
            # Convert lb -> mV for this channel.
            # Aggregate mV assumes 0.1 mV/lb at 10V; per-channel scales by ratio.
            mv = (total_lb + vib + noise) * self._m.mv_per_lb_at_10v * ratio
            # Add small sensor noise in mV domain.
            mv += random.gauss(0.0, 0.02)
            return mv

        n = int(self.average_samples)
        if n <= 1:
            return float(_one_sample())
        return float(sum(_one_sample() for _ in range(n)) / n)

    def get_gain_code(self, channel: int) -> int:
        if channel < 0 or channel > 7:
            raise ValueError(f"Invalid DAQ channel: {channel}")
        return int(self._gain_codes[int(channel)])

    def set_gain_code(self, channel: int, code: int) -> None:
        if channel < 0 or channel > 7:
            raise ValueError(f"Invalid DAQ channel: {channel}")
        c = int(code)
        if c < 0 or c > 7:
            raise ValueError(f"Invalid gain code: {code}")
        self._gain_codes[int(channel)] = c


class SimulatedMegaInd(MegaInd):
    def __init__(self, model: _SimModel) -> None:
        self._m = model
        self._t0 = time.monotonic()
        self.last_voltage_out = {}
        self.last_current_out = {}
        self._digital_in = {}
        self.last_relay = {}
        self.last_open_drain = {}

    def _t(self) -> float:
        return time.monotonic() - self._t0

    def read_analog_in_v(self, channel: int) -> float:
        # Channel 0 is treated as excitation monitor in the scaffold default.
        t = self._t()
        sag = self._m.excitation_sag_amp_v * (0.5 + 0.5 * math.sin(2 * math.pi * t / self._m.excitation_period_s))
        v = self._m.excitation_nom_v - sag + random.gauss(0.0, 0.03)
        return max(0.0, v)

    def write_analog_out_v(self, channel: int, volts: float) -> None:
        self.last_voltage_out[int(channel)] = float(volts)

    def write_analog_out_ma(self, channel: int, milliamps: float) -> None:
        self.last_current_out[int(channel)] = float(milliamps)

    def read_digital_in(self, channel: int) -> bool:
        return bool(self._digital_in.get(int(channel), False))

    def write_relay(self, channel: int, state: bool) -> None:
        self.last_relay[int(channel)] = bool(state)

    def write_open_drain(self, channel: int, value: float) -> None:
        self.last_open_drain[int(channel)] = float(value)


def SimulatedHardware(average_samples: int = 1) -> HardwareBundle:
    """Factory used by the scaffold entrypoint."""

    model = _SimModel(
        base_weight_lbs=_env_float("LCS_SIM_BASE_WEIGHT_LB", 120.0),
        step_amp_lbs=_env_float("LCS_SIM_STEP_AMP_LB", 60.0),
        step_period_s=_env_float("LCS_SIM_STEP_PERIOD_S", 18.0),
        excitation_nom_v=_env_float("LCS_SIM_EXC_NOM_V", 10.0),
        excitation_sag_amp_v=_env_float("LCS_SIM_EXC_SAG_AMP_V", 0.6),
        excitation_period_s=_env_float("LCS_SIM_EXC_PERIOD_S", 90.0),
        vib_amp_lb=_env_float("LCS_SIM_VIB_AMP_LB", 3.0),
        vib_hz=_env_float("LCS_SIM_VIB_HZ", 8.0),
        noise_lb_rms=_env_float("LCS_SIM_NOISE_LB_RMS", 0.8),
        channel_ratios=_env_ratios("LCS_SIM_CHANNEL_RATIOS", [0.25, 0.25, 0.25, 0.25]),
    )
    daq = SimulatedDaq(model, average_samples=average_samples)
    mega = SimulatedMegaInd(model)
    return HardwareBundle(daq=daq, megaind=mega)


