import time
import requests
import datetime
import sys

url = "http://172.16.190.25:8080/api/snapshot"

log_file_path = r"C:\Users\jthompson\Desktop\Scales\tmp_logs\live_performance_log_20260225.txt"

with open(log_file_path, "a") as f:
    f.write("Starting performance monitor. Press Ctrl+C to stop...\n")
    f.write("-" * 80 + "\n")
    f.flush()

print(f"Logging to: {log_file_path}")
print("Starting performance monitor. Press Ctrl+C to stop...")
print("-" * 80)

while True:
    try:
        resp = requests.get(url, timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            
            # Extract values
            wt = data.get("weight_lb", 0.0)
            raw = data.get("raw_lb", 0.0)  # Some snapshots use raw_lb or raw_signal_mv
            mv = data.get("raw_signal_mv", 0.0)
            stable = data.get("stable", False)
            
            # ZT details
            zt = data.get("zero_tracking", {})
            reason = zt.get("state", "unknown")
            hold = zt.get("hold_time_s", 0.0)
            
            # Offset
            offset_lbs = data.get("zero_offset_lbs", 0.0)
            offset_mv = data.get("zero_offset_mv", 0.0)
            
            # PLC
            plc = data.get("plc_output", {}).get("command", 0.0)
            
            # Format exactly like old logs
            now = datetime.datetime.now().strftime("%H:%M:%S")
            log_line = (
                f"{now} "
                f"wt={wt:7.1f} "
                f"raw={raw:7.1f} "
                f"mv={mv:.4f} "
                f"stable={str(stable):5s} "
                f"reason={reason:20s} "
                f"hold={hold:.1f}s "
                f"offset={offset_lbs:7.2f} "
                f"offset_mv={offset_mv:8.5f} "
                f"plc={plc:.4f}V"
            )
            print(log_line)
            
            with open(log_file_path, "a") as f:
                f.write(log_line + "\n")
                f.flush()
            
    except requests.exceptions.RequestException as e:
        err_msg = f"{datetime.datetime.now().strftime('%H:%M:%S')} ERROR: Could not connect to Pi ({e})"
        print(err_msg)
        with open(log_file_path, "a") as f:
            f.write(err_msg + "\n")
            f.flush()
        
    time.sleep(1)
