import os
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = os.getenv("ADMIN_ID", "")

if ADMIN_ID:
    try:
        ADMIN_ID = int(ADMIN_ID)
    except ValueError:
        ADMIN_ID = None
else:
    ADMIN_ID = None

DB_PATH = "bot_database.db"

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://mo-butlash.vercel.app/")

