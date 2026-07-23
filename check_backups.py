import os
import sqlite3

sqlite_files = ["bot_database_backup.db", "bot.db", "bot_database.db", "mo_bot.db", "mo_butlash.db", "database.db"]

for file in sqlite_files:
    if os.path.exists(file):
        try:
            conn = sqlite3.connect(file)
            cur = conn.cursor()
            tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
            if "requests" in tables:
                cnt = cur.execute("SELECT COUNT(*) FROM requests;").fetchone()[0]
                print(f"File {file}: requests count = {cnt}")
                if cnt > 0:
                    rows = cur.execute("SELECT id, description, created_by, status FROM requests LIMIT 5;").fetchall()
                    print(f"  Sample rows from {file}:", rows)
            else:
                print(f"File {file}: no 'requests' table")
            conn.close()
        except Exception as e:
            print(f"Error checking {file}: {e}")
