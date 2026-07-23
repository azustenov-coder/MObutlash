import asyncio
import os
import sys
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

async def main():
    db_url = os.environ.get('DATABASE_URL')
    async with await psycopg.AsyncConnection.connect(db_url, row_factory=dict_row) as db:
        async with db.cursor() as cur:
            await cur.execute("SELECT pg_get_serial_sequence('requests', 'id');")
            seq = await cur.fetchone()
            print("Requests ID Sequence:", seq)
            
            await cur.execute("SELECT MAX(id) as max_id FROM requests;")
            max_id = await cur.fetchone()
            print("Current MAX(id) in requests table:", max_id)

if __name__ == "__main__":
    asyncio.run(main())
