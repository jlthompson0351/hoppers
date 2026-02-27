import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import datetime

@dataclass
class Row:
    timestamp: datetime.datetime
    wt_lbs: float
    raw_lbs: float
    stable: bool

def parse_log(path: Path) -> List[Row]:
    rx = re.compile(
        r"^(?P<hh>\d\d):(?P<mm>\d\d):(?P<ss>\d\d)\s+"
        r"wt=\s*(?P<wt>[-\d.]+)\s+"
        r"raw=\s*(?P<raw>[-\d.]+)\s+"
    )
    out = []
    # Use an arbitrary date since logs only have time
    base_date = datetime.date(2026, 2, 18)
    
    for line in path.read_text(errors="ignore").splitlines():
        m = rx.search(line)
        if not m:
            continue
        
        t = datetime.datetime(
            year=base_date.year,
            month=base_date.month,
            day=base_date.day,
            hour=int(m["hh"]),
            minute=int(m["mm"]),
            second=int(m["ss"])
        )
        
        out.append(Row(
            timestamp=t,
            wt_lbs=float(m["wt"]),
            raw_lbs=float(m["raw"]),
            stable=("stable=True" in line)
        ))
    return out

def analyze_throughput(rows: List[Row], file_name: str):
    print(f"\n{'='*60}")
    print(f"ANALYSIS FOR: {file_name}")
    print(f"{'='*60}")
    
    if not rows:
        print("No data found.")
        return

    # A simple state machine to detect fill/dump cycles
    # State 0: Empty/Waiting (raw < empty_thr)
    # State 1: Filling (raw > empty_thr, increasing)
    # State 2: Dumping (raw dropped sharply)
    
    empty_thr = 20.0
    dump_drop_thr = 15.0 # lb per sec drop to trigger dump detection
    
    cycles = []
    
    in_dump = False
    peak_weight = 0.0
    peak_time = None
    
    fill_start_time = None
    empty_weight = rows[0].raw_lbs
    
    for i in range(1, len(rows)):
        prev = rows[i-1]
        cur = rows[i]
        
        dt = (cur.timestamp - prev.timestamp).total_seconds()
        if dt > 10:
            # Huge gap in log, reset state
            in_dump = False
            fill_start_time = None
            continue
            
        drop_rate = (prev.raw_lbs - cur.raw_lbs) / dt if dt > 0 else 0
        
        # Detect start of filling
        if not in_dump and fill_start_time is None and cur.raw_lbs > empty_weight + 5.0 and (cur.raw_lbs - prev.raw_lbs) > 0:
            fill_start_time = cur.timestamp
            
        # Update peak weight tracking while not dumping
        if not in_dump:
            if cur.raw_lbs > peak_weight:
                peak_weight = cur.raw_lbs
                peak_time = cur.timestamp
                
        # Detect dump trigger
        if not in_dump and drop_rate >= dump_drop_thr and prev.raw_lbs >= 20.0:
            in_dump = True
            
        # Detect end of dump (stabilized at low weight or stopped dropping)
        if in_dump and abs(drop_rate) < 2.0 and cur.raw_lbs < peak_weight - 15.0:
            in_dump = False
            dump_end_time = cur.timestamp
            post_dump_weight = cur.raw_lbs
            
            weight_dumped = peak_weight - post_dump_weight
            
            # Record cycle
            cycles.append({
                'dump_time': peak_time,
                'fill_duration': (peak_time - fill_start_time).total_seconds() if fill_start_time else 0,
                'dump_duration': (dump_end_time - peak_time).total_seconds(),
                'peak_weight': peak_weight,
                'weight_dumped': weight_dumped,
                'hour': peak_time.hour
            })
            
            # Reset for next cycle
            fill_start_time = None
            peak_weight = cur.raw_lbs
            empty_weight = cur.raw_lbs

    # --- Print Report ---
    if not cycles:
        print("No valid dump cycles detected.")
        return
        
    total_weight = sum(c['weight_dumped'] for c in cycles)
    total_time_minutes = (rows[-1].timestamp - rows[0].timestamp).total_seconds() / 60.0
    
    print(f"Total Run Time:   {total_time_minutes:.1f} minutes")
    print(f"Total Cycles:     {len(cycles)} dumps")
    print(f"Total Weight Ran: {total_weight:.1f} lbs\n")
    
    print(f"Avg Weight/Dump:  {total_weight/len(cycles):.1f} lbs")
    
    # Cycle times
    cycle_times = []
    for i in range(1, len(cycles)):
        cycle_times.append((cycles[i]['dump_time'] - cycles[i-1]['dump_time']).total_seconds())
        
    if cycle_times:
        avg_cycle = sum(cycle_times) / len(cycle_times)
        print(f"Avg Cycle Time:   {avg_cycle:.1f} seconds (Time between dumps)")
        
    fill_times = [c['fill_duration'] for c in cycles if c['fill_duration'] > 0]
    if fill_times:
        print(f"Avg Fill Time:    {sum(fill_times)/len(fill_times):.1f} seconds")
        
    dump_times = [c['dump_duration'] for c in cycles if c['dump_duration'] > 0]
    if dump_times:
        print(f"Avg Dump Time:    {sum(dump_times)/len(dump_times):.1f} seconds")
        
    # By hour breakdown
    print("\n--- HOURLY BREAKDOWN ---")
    hours = sorted(list(set(c['hour'] for c in cycles)))
    for h in hours:
        h_cycles = [c for c in cycles if c['hour'] == h]
        h_weight = sum(c['weight_dumped'] for c_cycles in h_cycles for c in [c_cycles])
        print(f"Hour {h:02d}:00 - {len(h_cycles):2d} dumps | {h_weight:6.1f} lbs processed")
        
    # Individual dumps (first 5 and last 5 if many)
    print("\n--- INDIVIDUAL DUMP LOG ---")
    print(f"{'Time':<10} | {'Peak Wt':<10} | {'Dumped Wt':<10} | {'Fill Time':<10} | {'Dump Time'}")
    print("-" * 65)
    
    for idx, c in enumerate(cycles):
        t_str = c['dump_time'].strftime("%H:%M:%S")
        print(f"{t_str:<10} | {c['peak_weight']:<7.1f} lb | {c['weight_dumped']:<7.1f} lb | {c['fill_duration']:<7.1f} s | {c['dump_duration']:<5.1f} s")

if __name__ == "__main__":
    paths = [
        Path(r"C:\Users\jthompson\Desktop\Scales\docs\archive\hour_log_1151.txt"),
        Path(r"C:\Users\jthompson\Desktop\Scales\docs\archive\shift_log_20260218_1310.txt")
    ]
    for p in paths:
        if p.exists():
            rows = parse_log(p)
            analyze_throughput(rows, p.name)
