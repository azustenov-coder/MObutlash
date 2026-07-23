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
            await cur.execute("SELECT status, COUNT(*) as cnt FROM requests GROUP BY status;")
            rows = await cur.fetchall()
            print("Requests in DB by status:", rows)
            
            await cur.execute("SELECT status, COUNT(*) as cnt FROM vehicles GROUP BY status;")
            veh_rows = await cur.fetchall()
            print("Vehicles in DB by status:", veh_rows)

if __name__ == "__main__":
    asyncio.run(main())
