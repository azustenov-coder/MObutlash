import asyncio
import os
import sqlite3
import sys
from dotenv import load_dotenv

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
import database as db

async def reset_inventory():
    print("Neon DB: Ombor qoldiqlarini tozalash boshlandi...")
    await db.init_db()
    async with db.db_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE inventory SET quantity = 0;")
            await conn.commit()
            print("OK Neon DB: Barcha ombor qoldiqlari 0 ga tenglashtirildi!")
    await db.close_db()

def reset_local_sqlite_inventory():
    sqlite_files = ["bot.db", "bot_database.db", "database.db", "mo_bot.db", "mo_butlash.db"]
    for file in sqlite_files:
        if os.path.exists(file):
            try:
                conn = sqlite3.connect(file)
                cur = conn.cursor()
                tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
                if "inventory" in tables:
                    cur.execute("UPDATE inventory SET quantity = 0;")
                    conn.commit()
                    print(f"OK SQLite ({file}): Ombor qoldiqlari 0 ga tenglashtirildi!")
                conn.close()
            except Exception as e:
                print(f"SQLite ({file}) xatosi: {e}")

async def main():
    await reset_inventory()
    reset_local_sqlite_inventory()
    print("\nOmbor bazasi to'liq 0 qilindi!")

if __name__ == "__main__":
    asyncio.run(main())
