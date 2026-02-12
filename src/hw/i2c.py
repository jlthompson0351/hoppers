from __future__ import annotations

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Known Sequent board base addresses
DAQ_24B8VIN_BASE_ADDRESS = 0x31  # Stack 0 = 0x31, Stack 1 = 0x32, etc.
MEGAIND_BASE_ADDRESS = 0x50      # Stack 0 = 0x50, Stack 1 = 0x51, etc.


@dataclass(frozen=True)
class DetectedBoard:
    """Information about a detected board."""
    board_type: str           # "daq24b8vin" or "megaind"
    address: int              # I2C address
    stack_id: int             # Computed stack ID (0-7)
    online: bool = True       # Whether communication succeeded


@dataclass(frozen=True)
class BoardDiscoveryResult:
    """Result of board discovery scan."""
    bus: int
    all_addresses: List[int]
    detected_boards: List[DetectedBoard]
    expected: Dict[str, int]           # Board type -> expected stack_id from config
    online_count: int                   # Number of expected boards that are online
    expected_count: int                 # Total number of expected boards
    raw_output: Optional[str] = None


@dataclass(frozen=True)
class I2CPresenceResult:
    ok: bool
    bus: int
    addresses: List[int]
    required: Dict[str, int]
    error: Optional[str]
    raw: Optional[str] = None


def _parse_i2cdetect_table(text: str) -> List[int]:
    """Parse `i2cdetect -y <bus>` output into a list of responding addresses.

    We treat any token other than '--' as a responding device (including 'UU').
    """

    addrs: List[int] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^[0-9a-fA-F]{2}:\s", line) is None:
            continue
        row, rest = line.split(":", 1)
        base = int(row, 16)
        tokens = [t for t in rest.strip().split() if t]
        # tokens correspond to columns 0..15
        for i, tok in enumerate(tokens[:16]):
            if tok == "--":
                continue
            addrs.append(base + i)
    return sorted(set(addrs))


def scan_i2c_bus(bus: int = 1, timeout_s: float = 2.0) -> Tuple[List[int], str]:
    """Return (addresses, raw_output) from i2cdetect scan."""

    exe = shutil.which("i2cdetect")
    if exe is None:
        # systemd services often run with a restricted PATH that omits /usr/sbin.
        for p in ("/usr/sbin/i2cdetect", "/usr/bin/i2cdetect", "/sbin/i2cdetect"):
            if Path(p).is_file():
                exe = p
                break
    if exe is None:
        raise FileNotFoundError("i2cdetect not found. Install i2c-tools and re-try.")
    proc = subprocess.run(  # noqa: S603,S607
        [exe, "-y", str(int(bus))],
        capture_output=True,
        text=True,
        timeout=float(timeout_s),
        check=True,
    )
    raw = proc.stdout or ""
    addrs = _parse_i2cdetect_table(raw)
    return addrs, raw


def _parse_addr(v) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        return int(s, 0)  # accepts "0x20" or "32"
    return None


def i2c_presence_check_from_config(cfg: dict) -> I2CPresenceResult:
    """Check I2C presence using commissioning-recorded addresses from config.

    This intentionally does NOT hardcode Sequent addresses. Instead, commissioning
    records each board's observed I2C address/stack ID, and the software verifies
    those required addresses are present at startup.
    """

    i2c_cfg = (cfg or {}).get("i2c") or {}
    bus = int(i2c_cfg.get("bus", 1))

    req = i2c_cfg.get("required_addresses") or i2c_cfg.get("required_devices") or {}
    required: Dict[str, int] = {}
    for name, val in (req or {}).items():
        addr = _parse_addr(val)
        if addr is None:
            continue
        required[str(name)] = int(addr)

    # Detect configured conflicts (e.g., both set to same address).
    seen = {}
    for name, addr in required.items():
        if addr in seen:
            return I2CPresenceResult(
                ok=False,
                bus=bus,
                addresses=[],
                required=required,
                error=f"I2C address conflict in config: '{seen[addr]}' and '{name}' both set to 0x{addr:02x}.",
            )
        seen[addr] = name

    # If nothing is configured, we can still scan for diagnostics, but we cannot enforce "missing board".
    if platform.system().lower() != "linux":
        if required:
            return I2CPresenceResult(
                ok=False,
                bus=bus,
                addresses=[],
                required=required,
                error="I2C presence check requires Linux (Raspberry Pi).",
            )
        return I2CPresenceResult(ok=True, bus=bus, addresses=[], required=required, error=None)

    try:
        addresses, raw = scan_i2c_bus(bus=bus)
    except Exception as e:  # noqa: BLE001
        if required:
            return I2CPresenceResult(
                ok=False,
                bus=bus,
                addresses=[],
                required=required,
                error=f"I2C scan failed: {e}",
            )
        return I2CPresenceResult(ok=True, bus=bus, addresses=[], required=required, error=None)

    if not required:
        return I2CPresenceResult(ok=True, bus=bus, addresses=addresses, required=required, error=None, raw=raw)

    missing = {name: addr for name, addr in required.items() if addr not in addresses}
    if missing:
        missing_str = ", ".join([f"{name}=0x{addr:02x}" for name, addr in missing.items()])
        return I2CPresenceResult(
            ok=False,
            bus=bus,
            addresses=addresses,
            required=required,
            error=f"Missing required I2C device(s) on bus {bus}: {missing_str}. Run `i2cdetect -y {bus}`.",
            raw=raw,
        )

    return I2CPresenceResult(ok=True, bus=bus, addresses=addresses, required=required, error=None, raw=raw)


def classify_address(address: int) -> Optional[DetectedBoard]:
    """Classify an I2C address as a known Sequent board type.

    Returns DetectedBoard if address matches a known board range, None otherwise.
    """
    # Check for 24b8vin DAQ (0x31-0x38)
    if DAQ_24B8VIN_BASE_ADDRESS <= address <= DAQ_24B8VIN_BASE_ADDRESS + 7:
        stack_id = address - DAQ_24B8VIN_BASE_ADDRESS
        return DetectedBoard(
            board_type="daq24b8vin",
            address=address,
            stack_id=stack_id,
            online=True,
        )

    # Check for MegaIND (0x50-0x57)
    if MEGAIND_BASE_ADDRESS <= address <= MEGAIND_BASE_ADDRESS + 7:
        stack_id = address - MEGAIND_BASE_ADDRESS
        return DetectedBoard(
            board_type="megaind",
            address=address,
            stack_id=stack_id,
            online=True,
        )

    return None


def discover_boards(cfg: dict, bus: Optional[int] = None) -> BoardDiscoveryResult:
    """Discover Sequent boards on the I2C bus.

    Scans the bus and classifies detected addresses into known board types.
    Compares against expected boards from config.

    Args:
        cfg: Application config dict
        bus: I2C bus number (defaults to config value or 1)

    Returns:
        BoardDiscoveryResult with detected boards and online status
    """
    i2c_cfg = (cfg or {}).get("i2c") or {}
    if bus is None:
        bus = int(i2c_cfg.get("bus", 1))

    # Get expected boards from config
    daq_cfg = (cfg or {}).get("daq") or (cfg or {}).get("daq24b8vin") or {}
    megaind_cfg = (cfg or {}).get("megaind") or {}

    expected: Dict[str, int] = {}
    if daq_cfg.get("stack_level") is not None:
        expected["daq24b8vin"] = int(daq_cfg.get("stack_level", 0))
    else:
        expected["daq24b8vin"] = 0  # Default stack 0

    if megaind_cfg.get("stack_level") is not None:
        expected["megaind"] = int(megaind_cfg.get("stack_level", 0))
    else:
        expected["megaind"] = 0  # Default stack 0

    expected_count = len(expected)

    # On non-Linux, return empty discovery with expected info
    if platform.system().lower() != "linux":
        return BoardDiscoveryResult(
            bus=bus,
            all_addresses=[],
            detected_boards=[],
            expected=expected,
            online_count=0,
            expected_count=expected_count,
            raw_output=None,
        )

    # Scan the bus
    try:
        addresses, raw = scan_i2c_bus(bus=bus)
    except Exception as e:  # noqa: BLE001
        return BoardDiscoveryResult(
            bus=bus,
            all_addresses=[],
            detected_boards=[],
            expected=expected,
            online_count=0,
            expected_count=expected_count,
            raw_output=f"Scan failed: {e}",
        )

    # Classify detected addresses
    detected_boards: List[DetectedBoard] = []
    for addr in addresses:
        board = classify_address(addr)
        if board is not None:
            detected_boards.append(board)

    # Count how many expected boards are online
    online_count = 0
    for board_type, exp_stack in expected.items():
        exp_addr = (
            DAQ_24B8VIN_BASE_ADDRESS + exp_stack
            if board_type == "daq24b8vin"
            else MEGAIND_BASE_ADDRESS + exp_stack
        )
        if exp_addr in addresses:
            online_count += 1

    return BoardDiscoveryResult(
        bus=bus,
        all_addresses=addresses,
        detected_boards=detected_boards,
        expected=expected,
        online_count=online_count,
        expected_count=expected_count,
        raw_output=raw,
    )


def get_boards_status(cfg: dict) -> Dict[str, Any]:
    """Get board status dict for state/snapshot.

    Returns a dict suitable for adding to LiveState with:
    - boards_online_count
    - boards_expected_count
    - boards_detected (list of detected board info dicts)
    - boards_online (dict of board_type -> bool)
    """
    result = discover_boards(cfg)

    # Build online status per board type
    boards_online: Dict[str, bool] = {}
    for board_type, exp_stack in result.expected.items():
        exp_addr = (
            DAQ_24B8VIN_BASE_ADDRESS + exp_stack
            if board_type == "daq24b8vin"
            else MEGAIND_BASE_ADDRESS + exp_stack
        )
        boards_online[board_type] = exp_addr in result.all_addresses

    # Convert detected boards to dicts
    detected = [
        {
            "type": b.board_type,
            "address": f"0x{b.address:02x}",
            "stack_id": b.stack_id,
        }
        for b in result.detected_boards
    ]

    return {
        "boards_online_count": result.online_count,
        "boards_expected_count": result.expected_count,
        "boards_detected": detected,
        "boards_online": boards_online,
        "boards_expected": result.expected,
    }

