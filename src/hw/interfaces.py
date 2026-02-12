from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class Daq24b8vin(Protocol):
    """Minimal interface for the Sequent 24b8vin-rpi board (or simulation)."""

    def read_differential_mv(self, channel: int) -> float:
        """Return differential input in millivolts for the given channel (0..7)."""

    def get_gain_code(self, channel: int) -> int:
        """Return the configured gain/range code for a channel (0..7)."""

    def set_gain_code(self, channel: int, code: int) -> None:
        """Set the configured gain/range code for a channel (0..7)."""


@runtime_checkable
class MegaInd(Protocol):
    """Minimal interface for the Sequent megaind-rpi board (or simulation)."""

    def read_analog_in_v(self, channel: int) -> float:
        """Return analog input in volts for the given channel."""

    def write_analog_out_v(self, channel: int, volts: float) -> None:
        """Write a 0-10V analog output channel."""

    def write_analog_out_ma(self, channel: int, milliamps: float) -> None:
        """Write a 4-20mA analog output channel."""

    def read_digital_in(self, channel: int) -> bool:
        """Read digital input (buttons, etc.)."""

    def write_relay(self, channel: int, state: bool) -> None:
        """Write to relay output (1..4)."""

    def write_open_drain(self, channel: int, value: float) -> None:
        """Write to open-drain PWM output (1..4, 0..100%)."""


@dataclass(frozen=True)
class HardwareBundle:
    """Convenience bundle passed into services."""

    daq: Daq24b8vin
    megaind: MegaInd
