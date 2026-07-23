import asyncio
import os
import sys
from dotenv import load_dotenv

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()
import database as db

async def main():
    await db.init_db()
    
    users = await db.get_approved_users()
    if not users:
        print("No approved users in DB")
        await db.close_db()
        return
        
    creator = users[0]
    
    req1 = await db.create_request(
        created_by=creator['telegram_id'],
        description="Test Zapchast Purchase Request 1",
        vehicle_name="Gazan-01",
        old_part_photo=None,
        qty_used=None,
        qty_left=None,
        request_type="purchase"
    )
    await db.add_request_item(req1, "Test Balon 2ta", 2, 0, 2)
    
    req2 = await db.create_request(
        created_by=creator['telegram_id'],
        description="Test Generator Repair Request 2",
        vehicle_name="Chakman 103",
        old_part_photo=None,
        qty_used=None,
        qty_left=None,
        request_type="repair"
    )
    await db.add_request_item(req2, "Generator Tamirlash", 1, 0, 1)
    
    print(f"Created test requests #{req1} and #{req2} in pending_approval status!")
    await db.close_db()

if __name__ == "__main__":
    asyncio.run(main())
