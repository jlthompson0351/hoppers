# Risk Register

## Scoring
- **Likelihood**: Low / Medium / High
- **Impact**: Low / Medium / High

## Risks
### R-01 Electrical Noise / Vibration Drives Instability
- **Cause**: Industrial vibration, nearby drives/contactors, poor shielding/grounding.
- **Effect**: Weight noise, false dump detection, calibration difficulty.
- **Likelihood**: High
- **Impact**: High
- **Mitigation**:
  - Shielded twisted pair for signals, separation from power wiring
  - Configure IIR filter + stability thresholds
  - Use ratiometric mode to reduce excitation-induced drift
  - Commissioning checklist includes noise verification

### R-02 Excitation Sag / Drift
- **Cause**: SlimPak supply droop, wiring resistance, temperature.
- **Effect**: Weight measurement drift if non-ratiometric.
- **Likelihood**: Medium
- **Impact**: High
- **Mitigation**:
  - Continuous excitation monitoring and logging
  - Warning/fault thresholds; safe output on fault
  - Ratiometric normalization mode (preferred)

### R-03 SD Card Corruption / Wear
- **Cause**: Power loss, frequent writes.
- **Effect**: Loss of logs/config; device fails to boot.
- **Likelihood**: Medium
- **Impact**: High
- **Mitigation**:
  - Limit write rate (downsample trends)
  - Use SQLite WAL mode (tune) and periodic housekeeping
  - Provide export/backups; consider industrial storage
  - Use UPS or power conditioning if needed

### R-04 Acquisition Loop Crash / Silent Failure
- **Cause**: Unhandled exceptions, hardware I/O errors.
- **Effect**: Stale output; unsafe control behavior.
- **Likelihood**: Medium
- **Impact**: High
- **Mitigation**:
  - Catch/log exceptions in loop and surface fault state
  - Force safe analog output on fault
  - systemd restart policy; optional watchdog integration

### R-05 Ground Loops / Reference Errors
- **Cause**: Multiple ground points, incorrect excitation reference to measurement AI.
- **Effect**: Excitation reading wrong; ratiometric math incorrect; noise injection.
- **Likelihood**: Medium
- **Impact**: High
- **Mitigation**:
  - Clear wiring instructions: EXC− reference must match AI reference
  - Single-point shield termination
  - Commissioning checks with DMM

### R-06 Non-Monotonic PLC Profile Mapping
- **Cause**: Bad point entry, PLC scaling changes, saturation.
- **Effect**: PWL interpolation becomes ambiguous; wrong outputs.
- **Likelihood**: Medium
- **Impact**: Medium
- **Mitigation**:
  - Validate mapping points monotonicity
  - Require multiple points and warn on non-monotonic data
  - Keep separate mapping per output mode

### R-07 Calibration Errors (Operator / Procedure)
- **Cause**: Unstable conditions, wrong known weights, poor point distribution.
- **Effect**: Incorrect scaling, poor accuracy.
- **Likelihood**: Medium
- **Impact**: High
- **Mitigation**:
  - Require stability before accepting points
  - Provide step-by-step procedure and validation checks
  - Log calibration events for traceability


