import sqlite3
conn = sqlite3.connect(r"D:/ghq/github.com/DwainYu/tft-agent-set17/data/tft.db")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print("Tables:", tables)
for t in tables:
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{t[0]}'")
    schema = cursor.fetchone()
    print(f"\n=== {t[0]} ===")
    print(schema[0] if schema else "N/A")
    cursor.execute(f"SELECT COUNT(*) FROM {t[0]}")
    cnt = cursor.fetchone()[0]
    print(f"Rows: {cnt}")
conn.close()