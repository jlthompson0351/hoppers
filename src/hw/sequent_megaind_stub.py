from __future__ import annotations

import logging
from typing import Dict

from src.hw.interfaces import MegaInd

log = logging.getLogger(__name__)


class SequentMegaIndStub(MegaInd):
    """Simulated wrapper for the Sequent megaind-rpi library.

    This stub provides a working simulation that stores output values and
    returns simulated input values for development and testing.
    
    Replace with SequentMegaInd (real driver) when running on Pi with hardware.

    Integration expectations (per commissioning assumptions):
    - A Sequent CLI tool is commonly available (often `megaind`; sometimes `megabas` depending on install) for commissioning analog IO.
    - Code must wrap:
      - analog outputs: 0–10V and 4–20mA
      - analog inputs: 0–10V (excitation monitoring)
      - opto digital inputs: operator buttons
    - Do not hardcode I2C addresses in code; commissioning records the selected stack ID/address and startup verifies presence.
    """

    def __init__(self, stack_id: int | None = None, i2c_addr: int | None = None, *_args, **_kwargs) -> None:
        self.stack_id = stack_id
        self.i2c_addr = i2c_addr
        # Simulated state storage
        self._analog_out_v: Dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        self._analog_out_ma: Dict[int, float] = {1: 4.0, 2: 4.0, 3: 4.0, 4: 4.0}
        self._analog_in_v: Dict[int, float] = {0: 10.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}  # ch0 = excitation
        self._digital_in: Dict[int, bool] = {1: False, 2: False, 3: False, 4: False}
        self._relay: Dict[int, bool] = {1: False, 2: False, 3: False, 4: False}
        self._open_drain: Dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        log.info(
            "SequentMegaIndStub initialized (SIMULATED mode). stack_id=%s",
            stack_id
        )

    def read_analog_in_v(self, channel: int) -> float:
        """Simulated analog input - returns preset values."""
        if channel == 0:
            channel = 1  # Treat 0 as channel 1 for legacy config
        val = self._analog_in_v.get(channel, 0.0)
        return val

    def write_analog_out_v(self, channel: int, volts: float) -> None:
        """Simulated 0-10V output - stores value for readback."""
        if channel == 0:
            channel = 1
        if not 1 <= channel <= 4:
            raise ValueError(f"Invalid analog output channel: {channel}")
        volts = max(0.0, min(10.0, float(volts)))
        self._analog_out_v[channel] = volts
        log.info("SIMULATED: write_analog_out_v(ch=%d, v=%.3f)", channel, volts)

    def write_analog_out_ma(self, channel: int, milliamps: float) -> None:
        """Simulated 4-20mA output - stores value for readback."""
        if channel == 0:
            channel = 1
        if not 1 <= channel <= 4:
            raise ValueError(f"Invalid current output channel: {channel}")
        milliamps = max(4.0, min(20.0, float(milliamps)))
        self._analog_out_ma[channel] = milliamps
        log.info("SIMULATED: write_analog_out_ma(ch=%d, mA=%.3f)", channel, milliamps)

    def read_digital_in(self, channel: int) -> bool:
        """Simulated digital input - returns preset values."""
        if not 1 <= channel <= 4:
            raise ValueError(f"Invalid digital input channel: {channel}")
        return self._digital_in.get(channel, False)

    def write_relay(self, channel: int, state: bool) -> None:
        """Simulated relay output."""
        if not 1 <= channel <= 4:
            raise ValueError(f"Invalid relay channel: {channel}")
        self._relay[channel] = bool(state)
        log.info("SIMULATED: write_relay(ch=%d, state=%s)", channel, state)

    def write_open_drain(self, channel: int, value: float) -> None:
        """Simulated open-drain output."""
        if not 1 <= channel <= 4:
            raise ValueError(f"Invalid open-drain channel: {channel}")
        self._open_drain[channel] = float(value)
        log.info("SIMULATED: write_open_drain(ch=%d, value=%.1f%%)", channel, value)

    def get_last_output_v(self, channel: int) -> float:
        """Get the last written voltage output (for UI readback in simulation)."""
        return self._analog_out_v.get(channel, 0.0)

    def get_last_output_ma(self, channel: int) -> float:
        """Get the last written current output (for UI readback in simulation)."""
        return self._analog_out_ma.get(channel, 4.0)

    def set_simulated_input(self, channel: int, volts: float) -> None:
        """Set a simulated input value (for testing)."""
        self._analog_in_v[channel] = volts


