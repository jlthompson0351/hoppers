from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class WatchdogHook:
    """Placeholder for hardware/software watchdog integration.

    In production, this could:
    - kick systemd watchdog (WatchdogSec + sd_notify)
    - toggle a digital output as a heartbeat
    - integrate with an external watchdog relay
    """

    def kick(self) -> None:
        # Scaffold: no-op
        return


