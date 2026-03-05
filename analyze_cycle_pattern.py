import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("/var/lib/loadcell-transmitter/data/app.sqlite3")
cursor = conn.cursor()

print("=" * 80)
print("CAROUSEL CYCLE TIME ANALYSIS")
print("=" * 80)
print("\nYour process: Hopper fills → dumps to basket → carousel → paint booth →")
print("             → spin back → dump basket on belt → hopper dumps again")
print()

# Get last 50 cycles to analyze pattern
cursor.execute("""
    SELECT id, timestamp_utc, processed_lbs, full_lbs, empty_lbs, duration_ms, confidence 
    FROM throughput_events 
    ORDER BY id DESC LIMIT 50
""")

rows = cursor.fetchall()

# Categorize cycles
cycles = []
for row in rows:
    id_, ts, processed_lbs, full_lbs, empty_lbs, duration_ms, confidence = row
    dt = datetime.fromisoformat(ts.replace('+00:00', ''))
    duration_sec = duration_ms / 1000
    cycles.append({
        'id': id_,
        'time': dt,
        'duration_sec': duration_sec,
        'duration_ms': duration_ms,
        'processed_lbs': processed_lbs,
        'full_lbs': full_lbs
    })

# Analyze by duration
fast_cycles = [c for c in cycles if c['duration_sec'] < 90]
medium_cycles = [c for c in cycles if 90 <= c['duration_sec'] < 110]
slow_cycles = [c for c in cycles if c['duration_sec'] >= 110]

print(f"--- CYCLE TIME BREAKDOWN (Last {len(cycles)} cycles) ---")
print()
print(f"FAST CYCLES ({len(fast_cycles)} cycles, < 90 sec):")
print(f"  Average: {sum(c['duration_sec'] for c in fast_cycles)/max(len(fast_cycles),1):.1f} sec")
print(f"  Range: {min((c['duration_sec'] for c in fast_cycles), default=0):.1f} - {max((c['duration_sec'] for c in fast_cycles), default=0):.1f} sec")
if fast_cycles:
    print(f"  When this happens: Empty basket (no wait for paint/dump cycle)")
    print(f"  Recent examples:")
    for c in fast_cycles[:3]:
        print(f"    - {c['time'].strftime('%H:%M:%S')}: {c['duration_sec']:.1f} sec ({c['processed_lbs']:.1f} lb)")

print()
print(f"MEDIUM CYCLES ({len(medium_cycles)} cycles, 90-110 sec):")
print(f"  Average: {sum(c['duration_sec'] for c in medium_cycles)/max(len(medium_cycles),1):.1f} sec")
print(f"  Range: {min((c['duration_sec'] for c in medium_cycles), default=0):.1f} - {max((c['duration_sec'] for c in medium_cycles), default=0):.1f} sec")
if medium_cycles:
    print(f"  When this happens: Normal painted part cycle")
    for c in medium_cycles[:3]:
        print(f"    - {c['time'].strftime('%H:%M:%S')}: {c['duration_sec']:.1f} sec ({c['processed_lbs']:.1f} lb)")

print()
print(f"SLOW CYCLES ({len(slow_cycles)} cycles, > 110 sec):")
print(f"  Average: {sum(c['duration_sec'] for c in slow_cycles)/max(len(slow_cycles),1):.1f} sec")
print(f"  Range: {min((c['duration_sec'] for c in slow_cycles), default=0):.1f} - {max((c['duration_sec'] for c in slow_cycles), default=0):.1f} sec")
if slow_cycles:
    print(f"  When this happens: Delayed cycle - hopper waited for painted parts")
    for c in slow_cycles[:3]:
        print(f"    - {c['time'].strftime('%H:%M:%S')}: {c['duration_sec']:.1f} sec ({c['processed_lbs']:.1f} lb)")

print()
print("=" * 80)
print("SEQUENCE ANALYSIS (Looking for fast-fast-slow-slow pattern)")
print("=" * 80)

# Look at last 20 in chronological order (reverse the reversed list)
recent = list(reversed(cycles[:20]))

print("\nLast 20 cycles (oldest first):")
print("-" * 60)
for i, c in enumerate(recent):
    marker = ""
    if c['duration_sec'] < 90:
        marker = " <-- FAST (empty basket)"
    elif c['duration_sec'] > 110:
        marker = " <-- SLOW (delayed)"
    print(f"{i+1:2d}. {c['time'].strftime('%H:%M:%S')} | {c['duration_sec']:6.1f} sec | {c['processed_lbs']:6.1f} lb{marker}")

# Check for the pattern user mentioned (first 2 fast, then slower)
print()
print("PATTERN CHECK:")
print("-" * 60)
if len(recent) >= 4:
    # Check if first 2 are typically faster than the rest
    first_two_avg = sum(c['duration_sec'] for c in recent[:2]) / 2
    rest_avg = sum(c['duration_sec'] for c in recent[2:]) / max(len(recent)-2, 1)
    
    if first_two_avg < rest_avg - 10:
        print(f"✓ PATTERN CONFIRMED: First 2 cycles avg {first_two_avg:.1f} sec")
        print(f"  Remaining cycles avg {rest_avg:.1f} sec")
        print(f"  Difference: {rest_avg - first_two_avg:.1f} seconds faster for empty baskets")
    else:
        print(f"  Recent first 2 cycles: {first_two_avg:.1f} sec average")
        print(f"  Remaining cycles: {rest_avg:.1f} sec average")
        print(f"  (Pattern may vary based on production schedule)")

print()
print("=" * 80)
print("KEY INSIGHTS")
print("=" * 80)
all_durations = [c['duration_sec'] for c in cycles]
print(f"• Fastest cycle: {min(all_durations):.1f} sec (empty basket, no paint wait)")
print(f"• Slowest cycle: {max(all_durations):.1f} sec (hopper held waiting for painted parts)")
print(f"• Average cycle: {sum(all_durations)/len(all_durations):.1f} sec")
print(f"• Typical filled-basket cycle: {sum(c['duration_sec'] for c in medium_cycles)/max(len(medium_cycles),1):.1f} sec")

# Calculate paint booth time estimate
if fast_cycles and medium_cycles:
    fast_avg = sum(c['duration_sec'] for c in fast_cycles) / len(fast_cycles)
    med_avg = sum(c['duration_sec'] for c in medium_cycles) / len(medium_cycles)
    paint_booth_estimate = med_avg - fast_avg
    print()
    print(f"ESTIMATED PAINT/SPIN CYCLE TIME: ~{paint_booth_estimate:.1f} seconds")
    print(f"  (Difference between normal cycle and empty-basket cycle)")
