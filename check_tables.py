import sqlite3

try:
    conn = sqlite3.connect('var/data/app.sqlite3')
    cursor = conn.cursor()

    print("=== Tables ===")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table in tables:
        print(table[0])
        
    print("\n=== Production Stats (last 5) ===")
    try:
        cursor.execute("SELECT * FROM production_stats ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()
        if not rows:
            print("No production stats found.")
        for row in rows:
            print(row)
    except sqlite3.OperationalError:
        print("Table 'production_stats' does not exist.")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
