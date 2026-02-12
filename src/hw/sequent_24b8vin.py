"""Real Sequent 24b8vin driver using smbus2.

Register map derived from .vendor/24b8vin-rpi/src/data.h
Gain scales from .vendor/24b8vin-rpi/src/analog.c
"""
from __future__ import annotations

import logging
import struct
import time
from typing import Optional

from src.hw.interfaces import Daq24b8vin

log = logging.getLogger(__name__)

# 24b8vin I2C register addresses (from data.h enum)
I2C_MEM_LEDS = 0            # LED bitmask (8 LEDs)
I2C_MEM_LED_SET = 1         # Set individual LED
I2C_MEM_LED_CLR = 2         # Clear individual LED
I2C_U_IN_VAL1_ADD = 3       # 8 channel voltages (8 x 4-byte IEEE 754 float)
I2C_GAIN_CH1 = 35           # 8 gain codes (1 byte each)
I2C_MEM_SR_SEL = 43         # Sample rate selector (0-5)
I2C_MEM_DIAG_TEMPERATURE = 44  # Board temperature (C)
I2C_MEM_DIAG_RASP_V = 45    # Pi voltage (2 bytes, mV)

# Firmware revision
I2C_MEM_REVISION_HW_MAJOR = 251
I2C_MEM_REVISION_HW_MINOR = 252
I2C_MEM_REVISION_MAJOR = 253
I2C_MEM_REVISION_MINOR = 254

# Base address (0x31 + stack_id)
BASE_ADDRESS = 0x31

# Gain code to full-scale voltage mapping (from analog.c)
# 0 => +/-24V, 1 => +/-12V, 2 => +/-6V, 3 => +/-3V,
# 4 => +/-1.5V, 5 => +/-0.75V, 6 => +/-0.37V, 7 => +/-0.18V
GAIN_FULL_SCALE_V = [24.0, 12.0, 6.0, 3.0, 1.5, 0.75, 0.37, 0.18]

# Sample rate codes (from analog.c SR_VAL array)
# 0 => 250 SPS, 1 => 500, 2 => 1000, 3 => 2000, 4 => 4000, 5 => 8000
SAMPLE_RATE_SPS = [250, 500, 1000, 2000, 4000, 8000]

# Default number of samples to average per read
DEFAULT_AVERAGE_SAMPLES = 2
SAMPLE_DELAY_S = 0.002  # 2ms


class Sequent24b8vin(Daq24b8vin):
    """Real Sequent 24b8vin driver using smbus2.

    Channels are 0-indexed (0..7).
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
        self.address = BASE_ADDRESS + self.stack_id
        self._bus: Optional[object] = None
        self._init_bus()

    def _init_bus(self) -> None:
        try:
            from smbus2 import SMBus
            self._bus = SMBus(self.i2c_bus)
            # Verify board presence by reading firmware revision
            major = self._bus.read_byte_data(self.address, I2C_MEM_REVISION_MAJOR)
            minor = self._bus.read_byte_data(self.address, I2C_MEM_REVISION_MINOR)
            log.info(
                "Sequent24b8vin initialized: stack=%d, bus=%d, addr=0x%02x, fw=%d.%d",
                self.stack_id, self.i2c_bus, self.address, major, minor
            )
        except ImportError as e:
            log.error("Failed to import smbus2: %s", e)
            raise
        except Exception as e:
            log.error(
                "Failed to initialize 24b8vin board at stack %d (addr 0x%02x): %s",
                self.stack_id, self.address, e
            )
            raise

    def _read_float(self, register: int) -> float:
        """Read a 32-bit float (IEEE 754 little-endian) from register."""
        if self._bus is None:
            raise RuntimeError("24b8vin bus not initialized")
        data = self._bus.read_i2c_block_data(self.address, register, 4)
        return struct.unpack("<f", bytes(data))[0]

    # ── Voltage reading ──────────────────────────────────────────────

    def read_differential_mv(self, channel: int) -> float:
        """Read differential input in millivolts for channel (0..7).

        Takes `average_samples` readings and returns the mean for noise reduction.
        """
        if not 0 <= channel <= 7:
            raise ValueError(f"Invalid DAQ channel: {channel}")

        register = I2C_U_IN_VAL1_ADD + (4 * channel)

        if self.average_samples <= 1:
            volts = self._read_float(register)
            return volts * 1000.0

        samples = []
        for i in range(self.average_samples):
            volts = self._read_float(register)
            samples.append(volts)
            if i < self.average_samples - 1:
                time.sleep(SAMPLE_DELAY_S)

        avg_volts = sum(samples) / len(samples)
        return avg_volts * 1000.0

    # ── Gain control ─────────────────────────────────────────────────

    def get_gain_code(self, channel: int) -> int:
        """Return the configured gain/range code for a channel (0..7)."""
        if not 0 <= channel <= 7:
            raise ValueError(f"Invalid DAQ channel: {channel}")
        if self._bus is None:
            raise RuntimeError("24b8vin bus not initialized")
        return self._bus.read_byte_data(self.address, I2C_GAIN_CH1 + channel)

    def set_gain_code(self, channel: int, code: int) -> None:
        """Set the gain/range code for a channel (0..7).

        Codes: 0=+/-24V, 1=+/-12V, 2=+/-6V, 3=+/-3V,
               4=+/-1.5V, 5=+/-750mV, 6=+/-370mV, 7=+/-180mV
        """
        if not 0 <= channel <= 7:
            raise ValueError(f"Invalid DAQ channel: {channel}")
        if not 0 <= code <= 7:
            raise ValueError(f"Invalid gain code: {code}")
        if self._bus is None:
            raise RuntimeError("24b8vin bus not initialized")
        self._bus.write_byte_data(self.address, I2C_GAIN_CH1 + channel, int(code))

    # ── Sample rate control ──────────────────────────────────────────

    def get_sample_rate(self) -> int:
        """Return current sample rate code (0-5).

        Codes: 0=250, 1=500, 2=1000, 3=2000, 4=4000, 5=8000 SPS
        """
        if self._bus is None:
            raise RuntimeError("24b8vin bus not initialized")
        return self._bus.read_byte_data(self.address, I2C_MEM_SR_SEL)

    def set_sample_rate(self, code: int) -> None:
        """Set sample rate code (0-5).

        Codes: 0=250, 1=500, 2=1000, 3=2000, 4=4000, 5=8000 SPS
        Lower rates give better noise rejection for load cell use.
        """
        if not 0 <= code <= 5:
            raise ValueError(f"Invalid sample rate code: {code} (must be 0-5)")
        if self._bus is None:
            raise RuntimeError("24b8vin bus not initialized")
        self._bus.write_byte_data(self.address, I2C_MEM_SR_SEL, int(code))
        log.info("Sample rate set to %d SPS (code %d)", SAMPLE_RATE_SPS[code], code)

    # ── Diagnostics ──────────────────────────────────────────────────

    def get_temperature(self) -> int:
        """Return board temperature in degrees Celsius."""
        if self._bus is None:
            raise RuntimeError("24b8vin bus not initialized")
        return self._bus.read_byte_data(self.address, I2C_MEM_DIAG_TEMPERATURE)

    def get_raspberry_voltage(self) -> float:
        """Return Raspberry Pi supply voltage in volts."""
        if self._bus is None:
            raise RuntimeError("24b8vin bus not initialized")
        data = self._bus.read_i2c_block_data(self.address, I2C_MEM_DIAG_RASP_V, 2)
        raw_mv = struct.unpack("<H", bytes(data))[0]
        return float(raw_mv) / 1000.0

    # ── LEDs ─────────────────────────────────────────────────────────

    def set_led(self, led: int, state: bool) -> None:
        """Set or clear an LED (1..8)."""
        if not 1 <= led <= 8:
            raise ValueError(f"Invalid LED: {led}")
        if self._bus is None:
            raise RuntimeError("24b8vin bus not initialized")
        reg = I2C_MEM_LED_SET if state else I2C_MEM_LED_CLR
        self._bus.write_byte_data(self.address, reg, 1 << (led - 1))
