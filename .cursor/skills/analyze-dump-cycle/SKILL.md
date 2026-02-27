# Analyze Dump Cycle

## Description
Automates the analysis of "Dump" cycles from the `acquisition.log` or database to report on drift, stability, and timing.

## Usage
"Analyze the last 5 dumps" or "Check dump stability"

## Implementation Steps
1.  **Fetch Data:** Read the last N hours of weight data from the logs/database.
2.  **Identify Dumps:** Look for rapid negative weight changes (e.g., > 50 lbs drop in < 2 seconds).
3.  **Extract Metrics:**
    -   **Pre-Dump Weight:** The stable weight before the drop.
    -   **Post-Dump Zero:** The stable weight *after* the drop and settle time.
    -   **Drift:** The difference between the *previous* Post-Dump Zero and the *current* Pre-Fill Zero.
    -   **Drop Duration:** Time from start of drop to bottom.
4.  **Report:**
    -   "Dump #1: 150.5 lbs -> 0.2 lbs (Drift: +0.2 lbs)"
    -   "WARNING: Dump #3 zeroed at 15.0 lbs (Potential material hang-up)."
