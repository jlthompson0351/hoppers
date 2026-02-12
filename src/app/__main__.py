from __future__ import annotations

import logging
import os
import signal
from pathlib import Path

from waitress import serve

from src.app import create_app
from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.hw.factory import create_hardware_bundle
from src.services.acquisition import AcquisitionService
from src.services.state import LiveState


def _configure_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    _configure_logging()
    log = logging.getLogger(__name__)

    var_dir = Path(os.environ.get("LCS_VAR_DIR", "var"))
    data_dir = var_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "app.sqlite3"

    ensure_db(db_path)
    repo = AppRepository(db_path)

    state = LiveState()

    # I2C presence check (optional -- for diagnostics)
    try:
        from src.hw.i2c import i2c_presence_check_from_config, get_boards_status
        cfg = repo.get_latest_config()
        i2c_res = i2c_presence_check_from_config(cfg)
        state.set(
            i2c_bus=i2c_res.bus,
            i2c_addresses=[f"0x{a:02x}" for a in i2c_res.addresses],
        )
        if not i2c_res.ok:
            repo.log_event(
                level="WARNING",
                code="I2C_PRESENCE_FAIL",
                message=i2c_res.error or "I2C presence check failed.",
                details={
                    "bus": i2c_res.bus,
                    "seen": [f"0x{a:02x}" for a in i2c_res.addresses],
                },
            )
        boards_status = get_boards_status(cfg)
        state.set(**boards_status)
    except Exception as e:
        log.warning("I2C presence check skipped: %s", e)

    # Initialize hardware (DAQ + MegaIND, no Watchdog)
    cfg = repo.get_latest_config()
    log.info("Initializing hardware (real mode only)...")
    hw_result = create_hardware_bundle(cfg)

    state.set(
        io_live=hw_result.ok,
        daq_online=hw_result.daq_online,
        megaind_online=hw_result.megaind_online,
        daq_error=hw_result.daq_error,
        megaind_error=hw_result.megaind_error,
    )

    if not hw_result.ok:
        parts = []
        if not hw_result.daq_online:
            parts.append(f"DAQ offline: {hw_result.daq_error or 'unknown'}")
        if not hw_result.megaind_online:
            parts.append(f"MegaIND offline: {hw_result.megaind_error or 'unknown'}")
        reason = "; ".join(parts) or "Hardware offline"
        state.set(fault=True, fault_reason=reason)
        repo.log_event(
            level="ERROR",
            code="HW_INIT_FAIL",
            message="Hardware initialization failed - will keep retrying",
            details={
                "daq_online": hw_result.daq_online,
                "megaind_online": hw_result.megaind_online,
                "daq_error": hw_result.daq_error,
                "megaind_error": hw_result.megaind_error,
            },
        )
        log.error("Hardware init failed: %s. Service will retry in background.", reason)
    else:
        log.info("Hardware initialized successfully - I/O is LIVE")

    # Start acquisition loop (handles retry if hardware offline)
    svc = AcquisitionService(
        hw=hw_result.bundle,
        repo=repo,
        state=state,
    )
    svc.start()

    app = create_app()
    app.config["LIVE_STATE"] = state
    app.config["REPO"] = repo
    app.config["ACQ_SERVICE"] = svc

    def _shutdown(*_args) -> None:
        log.info("Shutting down acquisition service...")
        svc.stop()
        svc.join(timeout=5.0)

    signal.signal(signal.SIGINT, lambda *_: _shutdown())
    signal.signal(signal.SIGTERM, lambda *_: _shutdown())

    host = os.environ.get("LCS_HOST", "127.0.0.1")
    port = int(os.environ.get("LCS_PORT", "8080"))
    log.info("Starting web UI on http://%s:%s", host, port)
    serve(app, host=host, port=port, threads=8)
    _shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
