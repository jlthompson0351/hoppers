#!/usr/bin/env python3
"""
Calibration verification helper
Reads current dashboard state via API and logs calibration points
"""

import json
import sys
import time
from urllib.request import urlopen
from urllib.error import URLError

DASHBOARD_URL = "http://localhost:8080/api/snapshot"


def get_snapshot():
    """Fetch current dashboard snapshot."""
    try:
        with urlopen(DASHBOARD_URL, timeout=2) as response:
            return json.loads(response.read())
    except URLError as e:
        print(f"❌ ERROR: Could not connect to dashboard: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Invalid JSON response: {e}")
        return None


def main():
    print("=== Calibration Verification Helper ===")
    print("")
    print("This script helps verify calibration by reading live dashboard data.")
    print("Place a known weight on the scale and press Enter to capture reading.")
    print("")
    
    readings = []
    
    while True:
        print("Options:")
        print("  [Enter] - Capture current reading")
        print("  [q] - Quit and show summary")
        
        choice = input("> ").strip().lower()
        
        if choice == "q":
            break
        
        # Capture reading
        snapshot = get_snapshot()
        if snapshot is None:
            print("Retrying...")
            time.sleep(1)
            continue
        
        weight_lb = snapshot.get("weight_lb", 0)
        stable = snapshot.get("stable", False)
        raw_signal = snapshot.get("raw_total_mv", 0)
        filtered_signal = snapshot.get("filtered_total_mv", 0)
        
        stable_str = "✓ STABLE" if stable else "✗ UNSTABLE"
        
        print("")
        print(f"Captured reading: {weight_lb:.2f} lb  [{stable_str}]")
        print(f"  Raw signal: {raw_signal:.3f} mV")
        print(f"  Filtered signal: {filtered_signal:.3f} mV")
        
        known_weight = input("Enter known weight (lb) or press Enter to skip: ").strip()
        
        if known_weight:
            try:
                known_weight_lb = float(known_weight)
                error_lb = weight_lb - known_weight_lb
                error_pct = (error_lb / known_weight_lb * 100) if known_weight_lb != 0 else 0
                
                readings.append({
                    "known_lb": known_weight_lb,
                    "measured_lb": weight_lb,
                    "error_lb": error_lb,
                    "error_pct": error_pct,
                    "stable": stable,
                    "raw_mv": raw_signal,
                    "filtered_mv": filtered_signal,
                })
                
                print(f"  Error: {error_lb:+.2f} lb ({error_pct:+.1f}%)")
            except ValueError:
                print("Invalid weight value")
        
        print("")
    
    # Summary
    if readings:
        print("")
        print("=== Calibration Verification Summary ===")
        print("")
        print(f"{'Known (lb)':<12} {'Measured (lb)':<15} {'Error (lb)':<12} {'Error (%)':<10} {'Stable':<8}")
        print("-" * 70)
        
        for r in readings:
            stable_mark = "✓" if r["stable"] else "✗"
            print(f"{r['known_lb']:<12.2f} {r['measured_lb']:<15.2f} {r['error_lb']:<+12.2f} {r['error_pct']:<+10.1f} {stable_mark:<8}")
        
        print("")
        
        # Statistics
        errors = [r["error_lb"] for r in readings]
        max_error = max(abs(e) for e in errors)
        avg_error = sum(errors) / len(errors)
        
        print(f"Max absolute error: {max_error:.2f} lb")
        print(f"Average error: {avg_error:.2f} lb")
        
        print("")
        
        # Pass/Fail
        TOLERANCE_LB = 2.0
        if max_error <= TOLERANCE_LB:
            print(f"✓ PASS - All readings within ±{TOLERANCE_LB} lb")
        else:
            print(f"✗ FAIL - Some readings exceed ±{TOLERANCE_LB} lb tolerance")
    
    print("")
    print("=== Verification Complete ===")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
