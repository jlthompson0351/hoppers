import sqlite3, json

DB = "/var/lib/loadcell-transmitter/data/app.sqlite3"
c = sqlite3.connect(DB)

row = c.execute("SELECT id, config_json FROM config_versions ORDER BY id DESC LIMIT 1").fetchone()
if row:
    cfg = json.loads(row[1])
    
    # Disable zero tracking
    zt = cfg.get("zero_tracking", {})
    old_enabled = zt.get("enabled")
    zt["enabled"] = False
    cfg["zero_tracking"] = zt
    
    # Clear zero offset
    scale = cfg.get("scale", {})
    old_zero = scale.get("zero_offset_mv", 0)
    scale["zero_offset_mv"] = 0.0
    scale["zero_offset_signal"] = 0.0
    scale["tare_offset_lbs"] = 0.0
    cfg["scale"] = scale
    
    # Clear PLC output zero offset
    out = cfg.get("output", {})
    old_plc_offset = out.get("plc_output_zero_offset", 0)
    out["plc_output_zero_offset"] = 0.0
    cfg["output"] = out
    
    c.execute("UPDATE config_versions SET config_json=? WHERE id=?", (json.dumps(cfg), row[0]))
    c.commit()
    
    print(f"Zero tracking: {old_enabled} -> False")
    print(f"Zero offset: {old_zero} -> 0.0")
    print(f"PLC output offset: {old_plc_offset} -> 0.0")
    print(f"Tare: -> 0.0")
    print("DONE - zero tracking disabled, all offsets cleared")
else:
    print("ERROR: no config found")

c.close()
