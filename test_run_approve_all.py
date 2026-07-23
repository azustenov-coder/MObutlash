import asyncio
import os
import sys
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()
import database as db
from handlers.controller import get_approval_target_status

async def test_approve():
    await db.init_db()
    pending = await db.get_requests_by_status('pending_approval')
    pending.extend(await db.get_requests_by_status('pending_admin_approval'))
    print(f"Found {len(pending)} pending requests.")
    
    couriers = await db.get_users_by_role('courier')
    print(f"Found {len(couriers)} couriers.")
    
    for req in pending:
        print(f"Req #{req['id']}: type={req.get('request_type')}, creator={req.get('creator_name')}")
        items = await db.get_request_items(req['id'])
        print(f"  Items count: {len(items)}")

    await db.close_db()

if __name__ == "__main__":
    asyncio.run(test_approve())
