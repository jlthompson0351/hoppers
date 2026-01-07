#!/usr/bin/env python3
"""
Analog output verification test log
Records weight readings and prompts for voltage measurements
Generates pass/fail report
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


def main():
    print("=== Analog Output Verification Test ===")
    print("")
    print("This script helps verify analog output voltage/current tracking.")
    print("It will capture dashboard weight and prompt you to measure output.")
    print("")
    
    # Get scale range from user
    max_weight = float(input("Enter max scale weight (lb) [default: 150]: ") or "150")
    output_mode = input("Output mode (V or mA) [default: V]: ").strip().upper() or "V"
    
    if output_mode == "V":
        output_min = 0.0
        output_max = 10.0
        unit = "V"
    else:
        output_min = 4.0
        output_max = 20.0
        unit = "mA"
    
    print("")
    print(f"Configuration: 0-{max_weight} lb → {output_min}-{output_max} {unit}")
    print("")
    
    test_points = []
    
    # Suggested test points
    test_percentages = [0, 25, 50, 75, 100]
    
    print("Suggested test points:")
    for pct in test_percentages:
        weight = max_weight * pct / 100
        expected_output = output_min + (pct / 100) * (output_max - output_min)
        print(f"  {pct}% → {weight:.1f} lb → {expected_output:.2f} {unit}")
    
    print("")
    print("Press Enter to begin test...")
    input()
    
    for pct in test_percentages:
        target_weight = max_weight * pct / 100
        expected_output = output_min + (pct / 100) * (output_max - output_min)
        
        print("")
        print("=" * 60)
        print(f"Test Point: {pct}% ({target_weight:.1f} lb)")
        print("=" * 60)
        
        if pct == 0:
            print("→ Remove all weights from scale")
        else:
            print(f"→ Place {target_weight:.1f} lb on scale (or closest available)")
        
        input("Press Enter when ready to measure...")
        
        # Wait for stable reading
        print("Waiting for stable reading...", end="", flush=True)
        stable = False
        attempts = 0
        max_attempts = 10
        
        while not stable and attempts < max_attempts:
            snapshot = get_snapshot()
            if snapshot:
                stable = snapshot.get("stable", False)
                weight_lb = snapshot.get("weight_lb", 0)
                
                if stable:
                    print(f" ✓ STABLE at {weight_lb:.2f} lb")
                    break
            
            print(".", end="", flush=True)
            time.sleep(1)
            attempts += 1
        
        if not stable:
            print(" ✗ UNSTABLE (timeout)")
            print("Proceeding anyway...")
            snapshot = get_snapshot()
            if snapshot:
                weight_lb = snapshot.get("weight_lb", 0)
        
        # Calculate expected output
        weight_pct = weight_lb / max_weight
        expected_output_actual = output_min + weight_pct * (output_max - output_min)
        
        print("")
        print(f"Dashboard reading: {weight_lb:.2f} lb")
        print(f"Expected output: {expected_output_actual:.2f} {unit}")
        print("")
        
        # Prompt for measurement
        measured_str = input(f"Enter measured output ({unit}) [or 's' to skip]: ").strip()
        
        if measured_str.lower() == 's':
            print("Skipped")
            continue
        
        try:
            measured_output = float(measured_str)
            error = measured_output - expected_output_actual
            error_pct = (error / (output_max - output_min)) * 100
            
            print(f"Measured: {measured_output:.2f} {unit}")
            print(f"Error: {error:+.2f} {unit} ({error_pct:+.1f}% of span)")
            
            # Tolerance
            if unit == "V":
                tolerance = 0.2  # ±0.2V
            else:
                tolerance = 0.5  # ±0.5mA
            
            passed = abs(error) <= tolerance
            pass_str = "✓ PASS" if passed else "✗ FAIL"
            print(f"Status: {pass_str} (tolerance: ±{tolerance} {unit})")
            
            test_points.append({
                "target_weight": target_weight,
                "measured_weight": weight_lb,
                "expected_output": expected_output_actual,
                "measured_output": measured_output,
                "error": error,
                "error_pct": error_pct,
                "passed": passed,
                "stable": stable,
            })
        
        except ValueError:
            print("Invalid measurement value")
    
    # Summary report
    print("")
    print("=" * 70)
    print("=== TEST SUMMARY ===")
    print("=" * 70)
    print("")
    
    if not test_points:
        print("No test points recorded")
        return
    
    print(f"{'Weight (lb)':<15} {'Output (exp)':<15} {'Output (meas)':<15} {'Error':<12} {'Status':<10}")
    print("-" * 70)
    
    for tp in test_points:
        pass_mark = "✓ PASS" if tp["passed"] else "✗ FAIL"
        print(
            f"{tp['measured_weight']:<15.2f} "
            f"{tp['expected_output']:<15.2f} "
            f"{tp['measured_output']:<15.2f} "
            f"{tp['error']:<+12.2f} "
            f"{pass_mark:<10}"
        )
    
    print("")
    
    # Overall result
    all_passed = all(tp["passed"] for tp in test_points)
    
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        failed_count = sum(1 for tp in test_points if not tp["passed"])
        print(f"✗ {failed_count} TEST(S) FAILED")
    
    print("")
    print("=== Test Complete ===")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
