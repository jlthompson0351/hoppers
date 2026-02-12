---
description: Code standards for industrial control systems - safety-critical requirements
alwaysApply: true
---

# Industrial Code Standards

## Safety-Critical Principles

### Fail-Safe Behavior (MANDATORY)
- **On hardware fault**: Outputs MUST go to safe state (0V or 4mA)
- **On exception**: Acquisition loop MUST NOT crash - catch and recover
- **On startup failure**: Service MUST stay up, retry hardware connection
- **Default state**: Outputs held at safe values until hardware confirmed online

### No Silent Failures
- ALL hardware errors MUST be logged to SQLite events table
- ALL I2C communication failures MUST be logged with context
- ALL exceptions MUST include traceback in logs
- UI MUST show clear fault indicators (I/O OFFLINE, not just blank)

### Defensive Programming
- Catch all hardware exceptions in acquisition loop
- Validate all user inputs before applying to hardware
- Bounds-check all calibration values
- Timeout all I2C operations (don't hang indefinitely)

## Hardware Interface Rules

### I2C Communication
- **Never hardcode I2C addresses**: Use constants in `src/hw/interfaces.py`
- **Always check board presence**: Startup must scan I2C bus and validate boards
- **Retry on failure**: If hardware read fails, retry with backoff (5s → 10s → 30s)
- **Hardware abstraction**: All hardware calls go through `src/hw/` interfaces

### Board-Specific Constants
```python
# Expected addresses (Stack ID 0)
DAQ_24B8VIN_ADDR = 0x31  # 24b8vin DAQ board
MEGAIND_ADDR = 0x50      # MegaIND I/O board
```

## Calibration & Settings

### Data Integrity
- **Immutable history**: Never delete calibration points, only add new ones
- **Versioned config**: All config changes go to `config_versions` table with timestamp
- **Atomic updates**: Settings changes must be transactional (SQLite BEGIN/COMMIT)
- **Validation**: New calibration points must be within 20% of previous or warn user

### Calibration Protection
- NEVER overwrite calibration during code deployment
- ALWAYS backup calibration before major updates
- ALWAYS verify calibration after firmware changes

## Real-Time Acquisition

### Loop Timing
- **Fixed rate**: Acquisition loop MUST maintain ~17Hz (configurable)
- **No blocking**: Never do network I/O or heavy disk writes in acquisition loop
- **Predictable**: Log if loop timing exceeds 100ms

### Thread Safety
- **Atomic state updates**: Use threading.Lock for shared state
- **No race conditions**: LiveState updates must be atomic
- **Timestamp everything**: All samples must have monotonic timestamp

## Code Quality

### Naming Conventions
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `SCREAMING_SNAKE_CASE`
- Hardware registers: Match vendor documentation

### Error Handling Pattern
```python
# Good pattern for hardware calls
try:
    value = self._read_channel(channel)
except OSError as e:
    logger.error(f"I2C read failed on channel {channel}: {e}")
    self._log_event("DAQ_READ_FAIL", {"channel": channel, "error": str(e)})
    return None  # Or safe default
```

### Logging Standards
- Use `loguru` for all logging
- Include context: what, where, why
- Log levels: ERROR (faults), WARNING (recoverable), INFO (operations), DEBUG (details)
