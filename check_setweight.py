import sqlite3

conn = sqlite3.connect("/var/lib/loadcell-transmitter/data/app.sqlite3")
cursor = conn.cursor()

print("=" * 60)
print("SET WEIGHT TABLES")
print("=" * 60)

# Check set_weight_current
print("\n--- set_weight_current ---")
cursor.execute("PRAGMA table_info(set_weight_current)")
cols = [r[1] for r in cursor.fetchall()]
print(f"Columns: {cols}")
cursor.execute("SELECT * FROM set_weight_current")
for row in cursor.fetchall():
    print(row)

# Check set_weight_history
print("\n--- set_weight_history ---")
cursor.execute("PRAGMA table_info(set_weight_history)")
cols = [r[1] for r in cursor.fetchall()]
print(f"Columns: {cols}")
cursor.execute("SELECT * FROM set_weight_history ORDER BY id DESC LIMIT 30")
for row in cursor.fetchall():
    print(row)

print(f"\n--- set_weight_history total count ---")
cursor.execute("SELECT COUNT(*) FROM set_weight_history")
print(f"Total records: {cursor.fetchone()[0]}")
