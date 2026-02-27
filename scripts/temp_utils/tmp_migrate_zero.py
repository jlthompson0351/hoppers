import sqlite3, json

DB = "/var/lib/loadcell-transmitter/data/app.sqlite3"
c = sqlite3.connect(DB)

row = c.execute("SELECT id, config_json FROM config_versions ORDER BY id DESC LIMIT 1").fetchone()
if row:
    cfg = json.loads(row[1])
    scale = cfg.get("scale", {})
    
    # Migrate: clear old signal-domain offsets, set weight-domain offset to 0
    old_mv = scale.get("zero_offset_mv", 0)
    scale["zero_offset_lbs"] = 0.0
    scale["zero_offset_mv"] = 0.0
    scale["zero_offset_signal"] = 0.0
    scale["tare_offset_lbs"] = 0.0
    cfg["scale"] = scale
    
    # Clear old plc_output_zero_offset
    out = cfg.get("output", {})
    out.pop("plc_output_zero_offset", None)
    cfg["output"] = out
    
    c.execute("UPDATE config_versions SET config_json=? WHERE id=?", (json.dumps(cfg), row[0]))
    c.commit()
    print(f"Migrated: old zero_offset_mv={old_mv} -> zero_offset_lbs=0.0")
    print("Cleared plc_output_zero_offset")
    print("DONE")

c.close()
