import sys

lines = open(sys.argv[1]).readlines()
prev_offset = None
for i, line in enumerate(lines):
    try:
        parts = line.split('offset=')
        if len(parts) < 2:
            continue
        offset = float(parts[1].strip().split()[0])
        if prev_offset is None or abs(offset - prev_offset) > 2.0:
            print(f"LINE {i+1}: {line.strip()}")
            if prev_offset is not None:
                print(f"  >>> JUMP: {prev_offset:.1f} -> {offset:.1f} (delta={offset-prev_offset:.1f})")
            print()
        prev_offset = offset
    except Exception:
        pass
