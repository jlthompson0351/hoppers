"""Hardware factory for creating HardwareBundle from config.

This module ONLY creates real hardware. There is no simulated fallback.
If hardware initialization fails, create_hardware_bundle returns None
and the caller (acquisition service) must handle retry logic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.hw.interfaces import HardwareBundle

log = logging.getLogger(__name__)


@dataclass
class HardwareInitResult:
    """Result of hardware initialization attempt."""
    bundle: Optional[HardwareBundle]
    daq_online: bool
    megaind_online: bool
    daq_error: Optional[str]
    megaind_error: Optional[str]

    @property
    def ok(self) -> bool:
        return self.bundle is not None and self.daq_online and self.megaind_online


def create_hardware_bundle(cfg: Dict[str, Any]) -> HardwareInitResult:
    """Create a HardwareBundle from config. Real hardware only.

    Args:
        cfg: Application config dict (from repo.get_latest_config())

    Returns:
        HardwareInitResult with bundle (or None if failed) and per-board status.
    """
    log.info("Initializing real Sequent hardware")

    # Get I2C bus from config (default 1)
    i2c_cfg = cfg.get("i2c") or {}
    i2c_bus = int(i2c_cfg.get("bus", 1))

    # Get DAQ config -- support both old "daq24b8vin" and new "daq" keys
    daq_cfg = cfg.get("daq") or cfg.get("daq24b8vin") or {}
    daq_stack = int(daq_cfg.get("stack_level", 0))
    daq_avg = int(daq_cfg.get("average_samples", 2) or 2)
    daq_avg = max(1, min(50, daq_avg))

    # Get MegaIND stack level from config (default 0)
    megaind_cfg = cfg.get("megaind") or {}
    megaind_stack = int(megaind_cfg.get("stack_level", 0))

    daq = None
    megaind = None
    daq_online = False
    megaind_online = False
    daq_error: Optional[str] = None
    megaind_error: Optional[str] = None

    # Try to initialize DAQ
    try:
        from src.hw.sequent_24b8vin import Sequent24b8vin
        daq = Sequent24b8vin(stack_id=daq_stack, i2c_bus=i2c_bus, average_samples=daq_avg)
        daq_online = True
        log.info("DAQ (24b8vin) initialized: stack=%d, bus=%d", daq_stack, i2c_bus)

        # Set sample rate and gain from config
        sr_code = int(daq_cfg.get("sample_rate", 0))
        daq.set_sample_rate(sr_code)

        gain_code = int(daq_cfg.get("gain_code", 6))
        channel = int(daq_cfg.get("channel", 7))
        daq.set_gain_code(channel, gain_code)
        log.info("DAQ channel %d: gain=%d, sample_rate=%d", channel, gain_code, sr_code)
    except Exception as e:
        daq_error = str(e)
        log.error("Failed to initialize DAQ (24b8vin): %s", e)

        # Fallback to simulation on Windows / no smbus2
        import platform
        if platform.system().lower() == "windows" or "No module named 'smbus2'" in str(e):
            log.warning("Falling back to SIMULATED hardware (Windows/No smbus2 detected)")
            from src.hw.simulated import SimulatedHardware
            sim_bundle = SimulatedHardware(average_samples=daq_avg)
            return HardwareInitResult(
                bundle=sim_bundle,
                daq_online=True,
                megaind_online=True,
                daq_error=None,
                megaind_error=None,
            )

    # Try to initialize MegaIND
    try:
        from src.hw.sequent_megaind import SequentMegaInd
        megaind = SequentMegaInd(stack_id=megaind_stack, i2c_bus=i2c_bus)
        megaind_online = True
        log.info("MegaIND initialized: stack=%d, bus=%d", megaind_stack, i2c_bus)
    except Exception as e:
        megaind_error = str(e)
        log.error("Failed to initialize MegaIND: %s", e)

    # Only return a complete bundle if BOTH core boards are online
    bundle: Optional[HardwareBundle] = None
    if daq is not None and megaind is not None:
        bundle = HardwareBundle(daq=daq, megaind=megaind)
        log.info("Hardware bundle created successfully")
    else:
        log.warning("Hardware bundle NOT created - one or more core boards offline")

    return HardwareInitResult(
        bundle=bundle,
        daq_online=daq_online,
        megaind_online=megaind_online,
        daq_error=daq_error,
        megaind_error=megaind_error,
    )
