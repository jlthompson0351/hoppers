"""Real Sequent MegaIND driver using smbus2.

Register map derived from .vendor/megaind-rpi/node-red-contrib-sm-ind/ind.js
and .vendor/megaind-rpi/src/megaind.h.
"""
from __future__ import annotations

import logging
import struct
from typing import Optional

from src.hw.interfaces import MegaInd

log = logging.getLogger(__name__)

# MegaIND I2C register addresses (from megaind.h and ind.js)
MEGAIND_BASE_ADDRESS = 0x50

# Register offsets
I2C_MEM_RELAY_VAL = 1
I2C_MEM_OPTO_IN_VAL = 3
I2C_MEM_U0_10_OUT_VAL1 = 4       # 0-10V outputs (4 channels, 2 bytes each)
I2C_MEM_I4_20_OUT_VAL1 = 12      # 4-20mA outputs (4 channels, 2 bytes each)
I2C_MEM_OD_PWM1 = 20             # Open drain PWM
I2C_MEM_U0_10_IN_VAL1 = 28       # 0-10V inputs (4 channels, 2 bytes each)
I2C_MEM_U_PM_10_IN_VAL1 = 36     # +/-10V inputs
I2C_MEM_I4_20_IN_VAL1 = 44       # 4-20mA inputs

# Diagnostics
I2C_MEM_DIAG_TEMPERATURE = 114   # CPU temp (1 byte)
I2C_MEM_DIAG_24V = 115           # Power voltage (2 bytes, mV)
I2C_MEM_DIAG_5V = 117            # Raspberry voltage (2 bytes, mV)

# Firmware revision
I2C_MEM_REVISION_MAJOR = 0x78    # 120
I2C_MEM_REVISION_MINOR = 0x79    # 121


class SequentMegaInd(MegaInd):
    """Real Sequent MegaIND driver using smbus2.

    Channels are 1-indexed (1..4) to match MegaIND physical labeling.
    """

    def __init__(self, stack_id: int = 0, i2c_bus: int = 1) -> None:
        self.stack_id = int(stack_id)
        self.i2c_bus = int(i2c_bus)
        self._address = MEGAIND_BASE_ADDRESS + self.stack_id
        self._bus: Optional[object] = None
        self._init_bus()

    def _init_bus(self) -> None:
        try:
            from smbus2 import SMBus
            self._bus = SMBus(self.i2c_bus)
            # Verify board presence by reading revision
            major = self._bus.read_byte_data(self._address, I2C_MEM_REVISION_MAJOR)
            minor = self._bus.read_byte_data(self._address, I2C_MEM_REVISION_MINOR)
            log.info(
                "SequentMegaInd initialized: stack=%d, bus=%d, addr=0x%02x, fw=%d.%d",
                self.stack_id, self.i2c_bus, self._address, major, minor
            )
        except ImportError as e:
            log.error("Failed to import smbus2: %s", e)
            raise
        except Exception as e:
            log.error(
                "Failed to initialize MegaIND at stack %d (addr 0x%02x): %s",
                self.stack_id, self._address, e
            )
            raise

    def _read_word(self, register: int) -> int:
        """Read a 16-bit little-endian word from register."""
        if self._bus is None:
            raise RuntimeError("MegaIND bus not initialized")
        data = self._bus.read_i2c_block_data(self._address, register, 2)
        return struct.unpack("<h", bytes(data))[0]

    def _write_word(self, register: int, value: int) -> None:
        """Write a 16-bit little-endian word to register."""
        if self._bus is None:
            raise RuntimeError("MegaIND bus not initialized")
        data = list(struct.pack("<H", int(value) & 0xFFFF))
        self._bus.write_i2c_block_data(self._address, register, data)

    def read_analog_in_v(self, channel: int) -> float:
        """Read analog input voltage for channel (1..4).

        Returns voltage in the range 0-10V.
        """
        # Support both 0-indexed and 1-indexed for backwards compatibility
        if channel == 0:
            channel = 1  # Treat 0 as channel 1 for legacy config
        if not 1 <= channel <= 4:
            raise ValueError(f"Invalid analog input channel: {channel}")

        register = I2C_MEM_U0_10_IN_VAL1 + (channel - 1) * 2
        raw_mv = self._read_word(register)
        return float(raw_mv) / 1000.0  # Convert mV to V

    def write_analog_out_v(self, channel: int, volts: float) -> None:
        """Write 0-10V analog output to channel (1..4)."""
        # Support both 0-indexed and 1-indexed
        if channel == 0:
            channel = 1
        if not 1 <= channel <= 4:
            raise ValueError(f"Invalid analog output channel: {channel}")

        # Clamp to valid range
        volts = max(0.0, min(10.0, float(volts)))
        raw_mv = int(volts * 1000.0)

        register = I2C_MEM_U0_10_OUT_VAL1 + (channel - 1) * 2
        self._write_word(register, raw_mv)

    def write_analog_out_ma(self, channel: int, milliamps: float) -> None:
        """Write 4-20mA analog output to channel (1..4)."""
        # Support both 0-indexed and 1-indexed
        if channel == 0:
            channel = 1
        if not 1 <= channel <= 4:
            raise ValueError(f"Invalid current output channel: {channel}")

        # Clamp to valid range (4-20mA)
        milliamps = max(4.0, min(20.0, float(milliamps)))
        raw_ua = int(milliamps * 1000.0)  # Convert to microamps

        register = I2C_MEM_I4_20_OUT_VAL1 + (channel - 1) * 2
        self._write_word(register, raw_ua)

    def read_digital_in(self, channel: int) -> bool:
        """Read digital (opto) input for channel (1..4)."""
        if not 1 <= channel <= 4:
            raise ValueError(f"Invalid digital input channel: {channel}")

        if self._bus is None:
            raise RuntimeError("MegaIND bus not initialized")

        opto_byte = self._bus.read_byte_data(self._address, I2C_MEM_OPTO_IN_VAL)
        return bool(opto_byte & (1 << (channel - 1)))

    def write_relay(self, channel: int, state: bool) -> None:
        """Write to relay output (1..4)."""
        if not 1 <= channel <= 4:
            raise ValueError(f"Invalid relay channel: {channel}")

        if self._bus is None:
            raise RuntimeError("MegaIND bus not initialized")

        # Read current relay states
        current = self._bus.read_byte_data(self._address, I2C_MEM_RELAY_VAL)
        if state:
            new_val = current | (1 << (channel - 1))
        else:
            new_val = current & ~(1 << (channel - 1))
        
        if current != new_val:
            self._bus.write_byte_data(self._address, I2C_MEM_RELAY_VAL, new_val)

    def write_open_drain(self, channel: int, value: float) -> None:
        """Write to open-drain PWM output (1..4, 0..100%)."""
        if not 1 <= channel <= 4:
            raise ValueError(f"Invalid open-drain channel: {channel}")

        # Clamp 0..100
        val_pct = max(0.0, min(100.0, float(value)))
        # Hardware expects 0..10000
        hw_val = int(val_pct * 100.0)

        register = I2C_MEM_OD_PWM1 + (channel - 1) * 2
        self._write_word(register, hw_val)

    def get_firmware_version(self) -> str:
        """Get firmware version string."""
        if self._bus is None:
            raise RuntimeError("MegaIND bus not initialized")
        major = self._bus.read_byte_data(self._address, I2C_MEM_REVISION_MAJOR)
        minor = self._bus.read_byte_data(self._address, I2C_MEM_REVISION_MINOR)
        return f"{major}.{minor}"

    def get_cpu_temperature(self) -> int:
        """Get CPU temperature in degrees Celsius."""
        if self._bus is None:
            raise RuntimeError("MegaIND bus not initialized")
        return self._bus.read_byte_data(self._address, I2C_MEM_DIAG_TEMPERATURE)

    def get_power_voltage(self) -> float:
        """Get power supply voltage in volts."""
        raw_mv = self._read_word(I2C_MEM_DIAG_24V)
        return float(raw_mv) / 1000.0

    def get_raspberry_voltage(self) -> float:
        """Get Raspberry Pi supply voltage in volts."""
        raw_mv = self._read_word(I2C_MEM_DIAG_5V)
        return float(raw_mv) / 1000.0
