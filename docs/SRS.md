# Software Requirements Specification (SRS)

## 1. Purpose
This document defines the software requirements for a **Raspberry Pi 4B Load Cell Scale Transmitter**. The system reads **3–4 load cells individually**, computes a total weight, filters for vibration, and outputs a **PLC-compatible analog signal** (**0–10V** or **4–20mA**). It also hosts a lightweight **Flask** web UI for configuration/calibration/diagnostics and logs production totals.

This replaces a SlimPak-style conditioner for signal conditioning, with the exception that **SlimPak Ultra provides excitation only**.

## 2. Scope
- **Input**: Differential load-cell mV signals via Sequent Microsystems **24b8vin-rpi** (DAQ 8-layer stackable HAT).
- **Excitation**: Provided externally by SlimPak Ultra (target ~10V). Software must **measure excitation** via Sequent **megaind-rpi** analog input and support **ratiometric normalization**.
- **Output**: Analog output to PLC via **megaind-rpi**, selectable between 0–10V and 4–20mA (separate physical outputs; channel selectable/configurable).
- **UI**: Local web UI (server-rendered templates; no heavy frontend framework).
- **Data**: SQLite persistence for config, calibration, events, trends, and production totals.
- **Robustness**: Must not silently stop acquisition; exceptions are logged; safe output on fault.

## 3. Definitions / Terms
- **Ratiometric**: Using normalized signal \( \text{signal\_mV} / \text{excitation\_V} \) so excitation sag does not bias weight.
- **Stable**: The measurement is sufficiently quiet for accepting calibration points and for dump/zero logic.
- **Dump event**: Rapid weight decrease indicating product discharge; used to estimate processed totals.

## 4. System Context
### 4.1 Hardware
- Raspberry Pi 4B
- Sequent Microsystems 24b8vin-rpi (DAQ) for load cells
- Sequent Microsystems megaind-rpi for analog output + digital inputs + excitation monitoring analog input
- Sequent Microsystems Super Watchdog HAT (UPS + watchdog)
- SlimPak Ultra used only for excitation output to load cells

### 4.2 Key Wiring Constraint
- **Excitation measurement**: Wire SlimPak EXC+ → MegaIND analog input 1 (0–10V IN) with EXC− as reference.
- **Power**: The system is powered by 24VDC. The **Super Watchdog HAT** must provide 5V power to the Raspberry Pi to enable UPS/watchdog functionality. Do not power the Pi via MegaIND or USB when the Watchdog is active.

## 5. Functional Requirements
### FR-01 Weight Range & Accuracy Goal
- **Range**: 0–300 lb.
- **Accuracy goal**: within ~0–5 lb in a vibrating industrial environment.

### FR-02 Acquisition Loop Independence
- Weight acquisition and output control shall run in a **background loop** independent of Flask request handling.
- Loop shall recover from transient errors (I/O exceptions) without exiting silently.

### FR-03 Sampling, Filtering, and Response
- Default tuning shall target approximately **250 ms** effective response.
- The system shall provide configurable filtering:
  - **IIR low-pass** (required)
  - **Stability detector** (required)
  - Optional future: Kalman filter (not required for scaffold)

### FR-04 Load Cell Channel Configuration
- Support **3 or 4 active load cells** (configurable).
- Support enabling/disabling any of the **8 DAQ channels**; disabled channels must not contribute to totals or diagnostics.

### FR-05 Total Weight Computation
- Total weight shall be computed as the sum of enabled channel contributions.
- Per-cell diagnostics shall be maintained:
  - raw differential signal (mV)
  - filtered signal
  - ratio contribution to total (for drift detection)

### FR-06 Excitation Measurement and Ratiometric Option
- The system shall continuously read excitation voltage via megaind 0–10V analog input.
- The system shall log excitation voltage trend.
- **Ratiometric normalization** mode shall be available and **enabled by default**:
  - Default ON: calibration and weight computation shall use normalized signal \(mV/V\).
  - A UI toggle shall allow disabling ratiometric mode for troubleshooting/diagnostics.
- Alarm thresholds shall be configurable:
  - **warning low excitation**
  - **fault very low excitation** (forces safe PLC output + UI fault indicator)

### FR-07 PLC Output Behavior
- Output mode shall be selectable:
  - **0–10V**
  - **4–20mA**
- Output shall be clamped to configured min/max weight range.
- On fault: force **safe output** (0V or 4mA) and set a fault status flag for UI.

### FR-08 PLC Profile Dynamic Mapping Wizard
Because PLC scaling may be unknown/legacy, the system shall support creating an output correction curve:
- Technician commands system to output a specified analog value (e.g., 3.25V).
- Technician enters what the PLC displays (lbs).
- From multiple samples across range, system builds a **piecewise-linear** mapping per output mode.
- The system shall choose the analog output required such that the PLC displays the **true** weight.
- Profiles shall be stored separately for `0_10V` and `4_20mA`.

### FR-09 Multi-Point Weight Calibration / Linearization
- Technician shall enter known weights (3–10 points).
- System shall save corresponding load-cell readings.
- System shall compute a piecewise-linear calibration curve converting signal → true weight.
- Stability detection shall be required before accepting a calibration point.

### FR-10 Self-Heal / Auto-Zero
- When “stable empty” is detected, the system may apply small auto-zero corrections.
- Auto-zero shall be transparent:
  - logged as events
  - visible in UI counters/warnings (“auto-zero applied X times”, “drift suspected”)

### FR-11 Drift Detection
- The system shall track each load cell’s contribution ratio over time.
- If ratio deviates beyond configurable threshold, system shall flag a drift warning and log an event.
- Historical trend data shall be maintained for at least 7 days (high-rate or downsampled).

### FR-12 Logging / Data Persistence
SQLite shall persist:
- Configuration changes (versioned)
- Calibration events and stored points
- PLC profile mapping points
- Faults/warnings (excitation, drift, stability, I/O errors)
- Excitation voltage trend
- Production totals: daily/weekly/monthly/yearly totals

### FR-13 Production Total Estimation (Dump Detection)
- When weight drops sharply (dump), assume processed weight ≈ (previous stable weight − new stable weight).
- This rule shall **not** require a drop-to-zero; it is based on stable-to-stable delta.
- Parameters shall be configurable:
  - dump detection threshold (lb)
  - stability window and required stability

## 6. Non-Functional Requirements
### NFR-01 Robustness
- Acquisition loop shall never stop silently.
- Any exception in I/O shall be caught, logged, and reflected in fault status as appropriate.

### NFR-02 Offline Operation
- System shall not require Internet access for normal operation.

### NFR-03 Maintainability / Testability
- Hardware interactions shall be behind dependency-injected interfaces.
- System shall gracefully handle hardware unavailability with automatic retry.

### NFR-04 SQLite / SD-card Durability
- The system shall enable SQLite **WAL mode** for improved resilience and concurrency.
- The system shall **batch inserts** for high-rate trend data to reduce write amplification.
- The system shall retain **high-rate trend data for approximately 7 days**, then downsample/roll up older data.
- Long-term records (totals and events) shall be stored as **aggregated records** suitable for retention and reporting.

### NFR-05 Security (Initial)
- This scaffold does not implement authentication. Commissioning environments must restrict network access appropriately until auth is added.

## 7. Assumptions / TBD
### Assumptions (current)
- Load cells are **4-wire full-bridge, ~3 mV/V** rated output.
- PLC analog output uses **separate physical outputs** for 0–10V and 4–20mA; software selects which output channel to drive per mode.

### TBD (confirm during commissioning)
- Exact channel mapping and scaling for Sequent boards (library API details).
- Exact PLC analog input impedance and grounding scheme at the panel.
- Environmental vibration spectrum; may require filter tuning changes.


