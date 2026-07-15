import asyncio
import os
import psycopg
from psycopg.rows import dict_row
from config import DB_PATH

async def main():
    try:
        async with await psycopg.AsyncConnection.connect(os.environ.get('DATABASE_URL'), row_factory=dict_row) as db:
            async with db.cursor() as cur:
                await cur.execute('''
                    SELECT
                        tc.table_name, 
                        kcu.column_name, 
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name,
                        rc.delete_rule
                    FROM 
                        information_schema.table_constraints AS tc 
                        JOIN information_schema.key_column_usage AS kcu
                          ON tc.constraint_name = kcu.constraint_name
                          AND tc.table_schema = kcu.table_schema
                        JOIN information_schema.constraint_column_usage AS ccu
                          ON ccu.constraint_name = tc.constraint_name
                          AND ccu.table_schema = tc.table_schema
                        JOIN information_schema.referential_constraints rc
                          ON rc.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public';
                ''')
                rows = await cur.fetchall()
                print("Foreign keys:")
                for r in rows:
                    print(r)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
