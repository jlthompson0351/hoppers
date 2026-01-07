from __future__ import annotations

import logging

from src.hw.interfaces import Daq24b8vin

log = logging.getLogger(__name__)


class Sequent24b8vinStub(Daq24b8vin):
    """Stub wrapper for the Sequent 24b8vin-rpi library.

    Replace the body of this class with real library calls when integrating on a Pi.
    Keep the interface stable so the rest of the system remains testable.

    Integration expectations (per commissioning assumptions):
    - A Sequent CLI tool is commonly available (often `24b8vin`) for testing/commissioning.
    - A Python module is expected to exist (e.g., `py24b8vin` or similar) supporting read-by-channel-index.
    - The board supports a selectable stack ID / I2C address; commissioning must record the chosen ID/address.
    """

    def __init__(self, stack_id: int | None = None, i2c_addr: int | None = None, *_args, **_kwargs) -> None:
        self.stack_id = stack_id
        self.i2c_addr = i2c_addr
        log.warning(
            "Sequent24b8vinStub initialized. Real Sequent integration not implemented in scaffold."
        )

    def read_differential_mv(self, channel: int) -> float:
        raise NotImplementedError(
            "Real Sequent 24b8vin-rpi integration is not implemented. Use simulated mode."
        )

    def get_gain_code(self, channel: int) -> int:
        raise NotImplementedError(
            "Real Sequent 24b8vin-rpi integration is not implemented. Use simulated mode."
        )

    def set_gain_code(self, channel: int, code: int) -> None:
        raise NotImplementedError(
            "Real Sequent 24b8vin-rpi integration is not implemented. Use simulated mode."
        )


