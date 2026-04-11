#!/usr/bin/env python3
"""Monitor all 4 opto inputs on MegaIND for 1 hour.
Read-only — does not interfere with the running loadcell-transmitter service.
Logs state changes and periodic heartbeats to /tmp/opto_monitor.log
"""
import struct
import time
from datetime import datetime, timezone

I2C_BUS = 1
MEGAIND_ADDR = 0x52
OPTO_REGISTER = 3
POLL_INTERVAL_S = 0.05       # 20 Hz — matches main app rate
HEARTBEAT_INTERVAL_S = 60
DURATION_S = 3600             # 1 hour
LOG_FILE = "/tmp/opto_monitor.log"

def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"

def read_opto_byte(bus):
    try:
        return bus.read_byte_data(MEGAIND_ADDR, OPTO_REGISTER)
    except Exception as e:
        return None

def main():
    from smbus2 import SMBus
    bus = SMBus(I2C_BUS)

    prev = [None, None, None, None]
    start = time.monotonic()
    last_heartbeat = start
    total_edges = [0, 0, 0, 0]

    with open(LOG_FILE, "w") as f:
        f.write(f"=== Opto Monitor Started at {ts()} ===\n")
        f.write(f"Polling at {1/POLL_INTERVAL_S:.0f} Hz for {DURATION_S/60:.0f} minutes\n")
        f.write(f"CH1=bit0  CH2=bit1  CH3=bit2  CH4=bit3\n\n")
        f.flush()

        print(f"Opto monitor running — logging to {LOG_FILE}")
        print(f"Press Ctrl+C to stop early\n")

        try:
            while (time.monotonic() - start) < DURATION_S:
                raw = read_opto_byte(bus)
                now = ts()
                elapsed = time.monotonic() - start

                if raw is None:
                    f.write(f"[{now}] I2C READ ERROR\n")
                    f.flush()
                    time.sleep(0.5)
                    continue

                states = [bool(raw & (1 << i)) for i in range(4)]

                for ch in range(4):
                    if prev[ch] is not None and states[ch] != prev[ch]:
                        edge = "RISING" if states[ch] else "FALLING"
                        total_edges[ch] += 1 if states[ch] else 0
                        line = f"[{now}] CH{ch+1} {edge}  (raw=0x{raw:02x})  edges_so_far={total_edges[ch]}"
                        f.write(line + "\n")
                        print(line)

                prev = states[:]

                if (time.monotonic() - last_heartbeat) >= HEARTBEAT_INTERVAL_S:
                    ch_str = "  ".join(f"CH{i+1}={'ON' if states[i] else 'off'}" for i in range(4))
                    edges_str = "  ".join(f"CH{i+1}={total_edges[i]}" for i in range(4))
                    hb = f"[{now}] HEARTBEAT {elapsed/60:.1f}min  {ch_str}  | rising_edges: {edges_str}"
                    f.write(hb + "\n")
                    f.flush()
                    print(hb)
                    last_heartbeat = time.monotonic()

                time.sleep(POLL_INTERVAL_S)

        except KeyboardInterrupt:
            f.write(f"\n[{ts()}] Stopped by user after {elapsed/60:.1f} min\n")

        summary = f"\n=== Summary at {ts()} ===\n"
        for i in range(4):
            summary += f"  CH{i+1}: {total_edges[i]} rising edges\n"
        f.write(summary)
        f.flush()
        print(summary)

    bus.close()

if __name__ == "__main__":
    main()
