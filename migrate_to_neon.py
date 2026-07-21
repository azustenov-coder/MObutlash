import asyncio
import os
import sqlite3
import sys
import psycopg
from psycopg.rows import dict_row

SQLITE_DB = "bot_database.db"
NEON_URL = os.environ.get("DATABASE_URL")

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        telegram_id BIGINT PRIMARY KEY,
        full_name TEXT,
        phone TEXT,
        role TEXT,
        is_approved INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        quantity INTEGER DEFAULT 0,
        category TEXT DEFAULT 'Qismlar'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS requests (
        id SERIAL PRIMARY KEY,
        created_by BIGINT,
        description TEXT,
        status TEXT,
        approved_by BIGINT,
        warehouse_released_by BIGINT,
        courier_id BIGINT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        vehicle_name TEXT,
        old_part_photo TEXT,
        installed_part_photo TEXT,
        quantity_used INTEGER,
        quantity_left INTEGER,
        request_type TEXT DEFAULT 'repair',
        price REAL DEFAULT 0.0,
        batch_id INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS request_items (
        id SERIAL PRIMARY KEY,
        request_id INTEGER,
        item_name TEXT,
        quantity_requested INTEGER,
        quantity_available INTEGER,
        quantity_missing INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vehicles (
        name TEXT PRIMARY KEY,
        status TEXT,
        reason TEXT,
        driver_name TEXT,
        driver_phone TEXT,
        vehicle_model TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bot_fsm (
        storage_key TEXT PRIMARY KEY,
        state TEXT,
        data JSONB NOT NULL DEFAULT '{}'::jsonb,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_transactions (
        id SERIAL PRIMARY KEY,
        item_name TEXT NOT NULL,
        type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        user_id BIGINT,
        request_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
]

async def migrate(reset: bool = False):
    if not NEON_URL:
        raise RuntimeError("DATABASE_URL environment variable is required")

    print("Connecting to Neon...")
    async with await psycopg.AsyncConnection.connect(NEON_URL) as pg_conn:
        if reset:
            print("Dropping tables to start fresh...")
            await pg_conn.execute("DROP TABLE IF EXISTS users, inventory, requests, request_items, vehicles, stock_transactions CASCADE")

        print("Creating tables in Neon...")
        for q in SCHEMA:
            await pg_conn.execute(q)
        await pg_conn.commit()
        print("Tables created.")

        print("Reading data from SQLite...")
        sl_conn = sqlite3.connect(SQLITE_DB)
        sl_conn.row_factory = sqlite3.Row
        cur = sl_conn.cursor()

        tables = ['users', 'inventory', 'requests', 'request_items', 'vehicles', 'stock_transactions']
        for table in tables:
            print(f"Migrating table {table}...")
            cur.execute(f"SELECT * FROM {table}")
            rows = cur.fetchall()
            if not rows:
                print(f"  Table {table} is empty.")
                continue
            
            columns = rows[0].keys()
            col_names = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(columns))
            
            insert_q = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
            
            for row in rows:
                values = tuple(row)
                await pg_conn.execute(insert_q, values)
            
            if table not in ['users', 'vehicles']:
                await pg_conn.execute(f"SELECT setval('{table}_id_seq', COALESCE((SELECT MAX(id)+1 FROM {table}), 1), false)")

            print(f"  Migrated {len(rows)} rows for {table}.")
            await pg_conn.commit()

        sl_conn.close()
        print("Migration complete!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(migrate(reset="--reset" in sys.argv))
