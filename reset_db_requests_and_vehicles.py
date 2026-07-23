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


async def reset_neon_database():
    print("Neon PostgreSQL bazasini tozalash boshlandi...")
    await db.init_db()
    async with db.db_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("TRUNCATE TABLE request_items, requests RESTART IDENTITY CASCADE;")
            await cur.execute("UPDATE vehicles SET status = 'soz', reason = NULL;")
            await cur.execute("DELETE FROM bot_fsm;")
            await conn.commit()
            print("OK Neon DB: Barcha zayavkalar (request_items va requests) o'chirildi!")
            print("OK Neon DB: Barcha mashinalar holati 'SOZ' (soz) ga o'tkazildi!")
            print("OK Neon DB: FSM holatlari tozalandi!")
    await db.close_db()


def reset_local_sqlite_databases():
    sqlite_files = ["bot.db", "bot_database.db", "database.db", "mo_bot.db", "mo_butlash.db"]
    for file in sqlite_files:
        if os.path.exists(file):
            try:
                conn = sqlite3.connect(file)
                cur = conn.cursor()
                tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
                if "request_items" in tables:
                    cur.execute("DELETE FROM request_items;")
                if "requests" in tables:
                    cur.execute("DELETE FROM requests;")
                if "vehicles" in tables:
                    cur.execute("UPDATE vehicles SET status = 'soz', reason = NULL;")
                if "bot_fsm" in tables:
                    cur.execute("DELETE FROM bot_fsm;")
                conn.commit()
                conn.close()
                print(f"OK SQLite ({file}): Zayavkalar va mashinalar holati tozalandi!")
            except Exception as e:
                print(f"SQLite ({file}) tozalashda xato: {e}")


async def main():
    await reset_neon_database()
    reset_local_sqlite_databases()
    print("\nBarcha bazalar to'liq tozalandi va mashinalar 'SOZ' holatiga o'tkazildi!")


if __name__ == "__main__":
    asyncio.run(main())
