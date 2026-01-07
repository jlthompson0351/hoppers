"""Real Sequent 24b8vin driver wrapping vendor library.

Uses the SM24b8vin library from .vendor/24b8vin-rpi/python.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Optional

from src.hw.interfaces import Daq24b8vin

log = logging.getLogger(__name__)

# Add vendor library to path
_VENDOR_PATH = Path(__file__).parent.parent.parent / ".vendor" / "24b8vin-rpi" / "python"
if str(_VENDOR_PATH) not in sys.path:
    sys.path.insert(0, str(_VENDOR_PATH))

# Default number of samples to average per read (reduces noise at hardware level)
DEFAULT_AVERAGE_SAMPLES = 2

# Delay between samples in seconds (allows ADC to settle)
SAMPLE_DELAY_S = 0.002  # 2ms


class Sequent24b8vin(Daq24b8vin):
    """Real Sequent 24b8vin driver using vendor SM24b8vin library.

    Wraps the vendor library methods to match our protocol interface.
    Channels are 0-indexed in our interface but 1-indexed in vendor lib.

    Features:
    - Hardware sample averaging: Takes N samples and averages for noise reduction.
    - Configurable samples per read via `average_samples` parameter.
    """

    def __init__(
        self,
        stack_id: int = 0,
        i2c_bus: int = 1,
        average_samples: int = DEFAULT_AVERAGE_SAMPLES,
    ) -> None:
        self.stack_id = int(stack_id)
        self.i2c_bus = int(i2c_bus)
        self.average_samples = max(1, int(average_samples))
        self._board: Optional[object] = None
        self._init_board()

    def _init_board(self) -> None:
        try:
            from SM24b8vin import SM24b8vin
            self._board = SM24b8vin(stack=self.stack_id, i2c=self.i2c_bus)
            log.info(
                "Sequent24b8vin initialized: stack=%d, bus=%d, version=%s",
                self.stack_id, self.i2c_bus, self._board.get_version()
            )
        except ImportError as e:
            log.error("Failed to import SM24b8vin library: %s", e)
            raise
        except Exception as e:
            log.error("Failed to initialize 24b8vin board at stack %d: %s", self.stack_id, e)
            raise

    def read_differential_mv(self, channel: int) -> float:
        """Read differential input in millivolts for channel (0..7).

        Vendor library uses 1-indexed channels and returns volts.
        Takes `average_samples` readings and returns the mean for noise reduction.
        """
        if not 0 <= channel <= 7:
            raise ValueError(f"Invalid DAQ channel: {channel}")
        if self._board is None:
            raise RuntimeError("24b8vin board not initialized")

        # Vendor uses 1-indexed channels
        vendor_ch = channel + 1

        if self.average_samples <= 1:
            # Single sample (no averaging)
            volts = float(self._board.get_u_in(vendor_ch))
            return volts * 1000.0

        # Take multiple samples and average for noise reduction
        samples = []
        for i in range(self.average_samples):
            volts = float(self._board.get_u_in(vendor_ch))
            samples.append(volts)
            # Small delay between samples to let ADC settle (skip after last)
            if i < self.average_samples - 1:
                time.sleep(SAMPLE_DELAY_S)

        avg_volts = sum(samples) / len(samples)
        return avg_volts * 1000.0  # Convert to mV

    def get_gain_code(self, channel: int) -> int:
        """Return the configured gain/range code for a channel (0..7)."""
        if not 0 <= channel <= 7:
            raise ValueError(f"Invalid DAQ channel: {channel}")
        if self._board is None:
            raise RuntimeError("24b8vin board not initialized")

        # Vendor uses 1-indexed channels
        return int(self._board.get_gain(channel + 1))

    def set_gain_code(self, channel: int, code: int) -> None:
        """Set the configured gain/range code for a channel (0..7)."""
        if not 0 <= channel <= 7:
            raise ValueError(f"Invalid DAQ channel: {channel}")
        if not 0 <= code <= 7:
            raise ValueError(f"Invalid gain code: {code}")
        if self._board is None:
            raise RuntimeError("24b8vin board not initialized")

        # Vendor uses 1-indexed channels
        self._board.set_gain(channel + 1, int(code))
