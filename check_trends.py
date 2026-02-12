import sqlite3

try:
    conn = sqlite3.connect('var/data/app.sqlite3')
    cursor = conn.cursor()

    print("=== Trends Total (last 5) ===")
    try:
        cursor.execute("SELECT * FROM trends_total ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()
        if not rows:
            print("No trends data found.")
        for row in rows:
            print(row)
    except Exception as e:
        print(f"Error reading trends_total: {e}")

    print("\n=== Production Dumps (last 5) ===")
    try:
        cursor.execute("SELECT * FROM production_dumps ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()
        if not rows:
            print("No dumps found.")
        for row in rows:
            print(row)
    except Exception as e:
        print(f"Error reading production_dumps: {e}")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
