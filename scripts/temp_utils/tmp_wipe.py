import sqlite3, json

DB = "/var/lib/loadcell-transmitter/data/app.sqlite3"
c = sqlite3.connect(DB)

# Count before
cal_count = c.execute("SELECT COUNT(*) FROM calibration_points").fetchone()[0]
plc_count = c.execute("SELECT COUNT(*) FROM plc_profile_points").fetchone()[0]
print(f"Before: {cal_count} calibration points, {plc_count} output match points")

# Delete all
c.execute("DELETE FROM calibration_points")
c.execute("DELETE FROM plc_profile_points")

# Reset PLC output zero offset and zero offset in config
row = c.execute("SELECT id, config_json FROM config_versions ORDER BY id DESC LIMIT 1").fetchone()
if row:
    cfg = json.loads(row[1])
    # Reset output zero offset
    out = cfg.get("output", {})
    out["plc_output_zero_offset"] = 0.0
    cfg["output"] = out
    # Reset zero offset
    scale = cfg.get("scale", {})
    scale["zero_offset_mv"] = 0.0
    scale["zero_offset_signal"] = 0.0
    scale["tare_offset_lbs"] = 0.0
    cfg["scale"] = scale
    c.execute("UPDATE config_versions SET config_json=? WHERE id=?", (json.dumps(cfg), row[0]))
    print("Config reset: plc_output_zero_offset=0, zero_offset=0, tare=0")

c.commit()

# Count after
cal_count = c.execute("SELECT COUNT(*) FROM calibration_points").fetchone()[0]
plc_count = c.execute("SELECT COUNT(*) FROM plc_profile_points").fetchone()[0]
print(f"After: {cal_count} calibration points, {plc_count} output match points")
print("DONE - clean slate")

c.close()
