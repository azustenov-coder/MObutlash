import aiosqlite
import datetime
from config import DB_PATH

PREDEFINED_VEHICLES = [
    "102", "103", "106", "107", "108", "109", "112", "115", "117", "122",
    "123", "477", "478", "480", "481", "482", "484", "485", "488", "492",
    "493", "494", "497", "615", "617", "499", "489", "487", "124", "125",
    "126", "127", "9154", "9155", "9156", "9157", "9158", "9159", "361",
    "362", "364", "809", "810", "961"
]

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Foydalanuvchilar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'guest',
                is_approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        # Zayavkalar (so'rovlar) jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_by INTEGER NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_approval',
                approved_by INTEGER,
                warehouse_released_by INTEGER,
                courier_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (created_by) REFERENCES users (telegram_id),
                FOREIGN KEY (approved_by) REFERENCES users (telegram_id),
                FOREIGN KEY (warehouse_released_by) REFERENCES users (telegram_id),
                FOREIGN KEY (courier_id) REFERENCES users (telegram_id)
            )
        """)
        # Ombor zaxirasi jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                quantity INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Zayavka tarkibidagi mahsulotlar
        await db.execute("""
            CREATE TABLE IF NOT EXISTS request_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity_requested INTEGER NOT NULL,
                quantity_available INTEGER NOT NULL DEFAULT 0,
                quantity_missing INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (request_id) REFERENCES requests (id)
            )
        """)
        # Check if category column exists, if not add it
        async with db.execute("PRAGMA table_info(inventory)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'category' not in columns:
                await db.execute("ALTER TABLE inventory ADD COLUMN category TEXT NOT NULL DEFAULT 'butlovchi'")
        
        # Check if vehicle_name and old_part_photo exist in requests
        async with db.execute("PRAGMA table_info(requests)") as cursor:
            req_cols = [row[1] for row in await cursor.fetchall()]
            if 'vehicle_name' not in req_cols:
                await db.execute("ALTER TABLE requests ADD COLUMN vehicle_name TEXT")
            if 'old_part_photo' not in req_cols:
                await db.execute("ALTER TABLE requests ADD COLUMN old_part_photo TEXT")
            if 'installed_part_photo' not in req_cols:
                await db.execute("ALTER TABLE requests ADD COLUMN installed_part_photo TEXT")
            if 'quantity_used' not in req_cols:
                await db.execute("ALTER TABLE requests ADD COLUMN quantity_used INTEGER")
            if 'quantity_left' not in req_cols:
                await db.execute("ALTER TABLE requests ADD COLUMN quantity_left INTEGER")
            if 'request_type' not in req_cols:
                await db.execute("ALTER TABLE requests ADD COLUMN request_type TEXT NOT NULL DEFAULT 'repair'")
            if 'price' not in req_cols:
                await db.execute("ALTER TABLE requests ADD COLUMN price INTEGER DEFAULT 0")
                
        # Vehicles table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                name TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'soz',
                reason TEXT
            )
        """)
        async with db.execute("PRAGMA table_info(vehicles)") as cursor:
            veh_cols = [row[1] for row in await cursor.fetchall()]
            if 'reason' not in veh_cols:
                await db.execute("ALTER TABLE vehicles ADD COLUMN reason TEXT")
                
        for veh in PREDEFINED_VEHICLES:
            await db.execute("INSERT OR IGNORE INTO vehicles (name, status) VALUES (?, 'soz')", (veh,))
            
        # Tranzaksiyalar jadvali (kirim / chiqim tarixi)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stock_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                user_id INTEGER,
                request_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (telegram_id),
                FOREIGN KEY (request_id) REFERENCES requests (id)
            )
        """)
            
        await db.commit()


# --- FOYDALANUVCHILAR BILAN ISHLASH ---

async def add_user(telegram_id: int, full_name: str, phone: str, role: str):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        # Agar bu bazadagi birinchi foydalanuvchi bo'lsa, uni super_admin qilamiz (avtomatik ravishda tasdiqlangan holatda)
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        count = row[0] if row else 0
        
        from config import ADMIN_ID
        is_approved = 0
        final_role = role
        if ADMIN_ID and telegram_id == ADMIN_ID:
            final_role = 'super_admin'
            is_approved = 1
        elif count == 0:
            final_role = 'super_admin'
            is_approved = 1
            
        await db.execute("""
            INSERT INTO users (telegram_id, full_name, phone, role, is_approved, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name = excluded.full_name,
                phone = excluded.phone,
                role = excluded.role,
                is_approved = excluded.is_approved
        """, (telegram_id, full_name, phone, final_role, is_approved, now))
        await db.commit()
        return final_role, is_approved

async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            return await cursor.fetchone()

async def get_pending_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE is_approved = 0") as cursor:
            return await cursor.fetchall()

async def approve_user(telegram_id: int, role: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if role:
            await db.execute("UPDATE users SET is_approved = 1, role = ? WHERE telegram_id = ?", (role, telegram_id))
        else:
            await db.execute("UPDATE users SET is_approved = 1 WHERE telegram_id = ?", (telegram_id,))
        await db.commit()

async def reject_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        await db.commit()

async def update_user_role(telegram_id: int, role: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET role = ? WHERE telegram_id = ?", (role, telegram_id))
        await db.commit()

async def get_users_by_role(role: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE role = ? AND is_approved = 1", (role,)) as cursor:
            return await cursor.fetchall()

# --- ZAYAVKALAR (SO'ROVLAR) BILAN ISHLASH ---

async def create_request(created_by: int, description: str, vehicle_name: str = None, old_part_photo: str = None, qty_used: int = None, qty_left: int = None, request_type: str = 'repair'):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        cursor = await db.execute("""
            INSERT INTO requests (created_by, description, status, created_at, updated_at, vehicle_name, old_part_photo, quantity_used, quantity_left, request_type)
            VALUES (?, ?, 'pending_approval', ?, ?, ?, ?, ?, ?, ?)
        """, (created_by, description, now, now, vehicle_name, old_part_photo, qty_used, qty_left, request_type))
        await db.commit()
        return cursor.lastrowid

async def get_request(request_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.*, 
                   u.full_name as creator_name, u.phone as creator_phone,
                   app.full_name as approver_name,
                   wh.full_name as warehouseman_name,
                   cour.full_name as courier_name
            FROM requests r
            LEFT JOIN users u ON r.created_by = u.telegram_id
            LEFT JOIN users app ON r.approved_by = app.telegram_id
            LEFT JOIN users wh ON r.warehouse_released_by = wh.telegram_id
            LEFT JOIN users cour ON r.courier_id = cour.telegram_id
            WHERE r.id = ?
        """, (request_id,)) as cursor:
            return await cursor.fetchone()

async def update_request_status(request_id: int, status: str, updated_by_id: int, role: str):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        if role in ['manager', 'super_admin']:
            if status in ['approved', 'pending_admin_approval']:
                await db.execute("""
                    UPDATE requests SET status = ?, approved_by = ?, updated_at = ? WHERE id = ?
                """, (status, updated_by_id, now, request_id))
            else:
                await db.execute("""
                    UPDATE requests SET status = ?, updated_at = ? WHERE id = ?
                """, (status, now, request_id))
        elif role == 'warehouseman':
            await db.execute("""
                UPDATE requests SET status = ?, warehouse_released_by = ?, updated_at = ? WHERE id = ?
            """, (status, updated_by_id, now, request_id))
        elif role == 'courier':
            await db.execute("""
                UPDATE requests SET status = ?, courier_id = ?, updated_at = ? WHERE id = ?
            """, (status, updated_by_id, now, request_id))
        else:
            await db.execute("""
                UPDATE requests SET status = ?, updated_at = ? WHERE id = ?
            """, (status, now, request_id))
        await db.commit()

async def update_installed_part_photo(request_id: int, photo_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute("""
            UPDATE requests SET installed_part_photo = ?, updated_at = ? WHERE id = ?
        """, (photo_id, now, request_id))
        await db.commit()

async def get_broken_vehicles():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM vehicles WHERE status = 'nosoz'") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def get_healthy_vehicles():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM vehicles WHERE status = 'soz'") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def get_all_vehicles():
    return PREDEFINED_VEHICLES

async def update_vehicle_status(name: str, status: str, reason: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE vehicles SET status = ?, reason = ? WHERE name = ?", (status, reason, name.strip()))
        await db.commit()

async def check_vehicle_active_requests(name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*) FROM requests 
            WHERE vehicle_name = ? AND status NOT IN ('completed', 'rejected')
        """, (name.strip(),)) as cursor:
            row = await cursor.fetchone()
            return row[0] > 0 if row else False

async def update_request_installation_details(request_id: int, photo_id: str, items_used_map: dict = None):
    req = await get_request(request_id)
    creator_id = req['created_by'] if req else None
    now = datetime.datetime.now().isoformat()
    
    items = await get_request_items(request_id)
    if items_used_map is None:
        items_used_map = {str(item['id']): item['quantity_requested'] for item in items}
        
    total_qty_used = sum(int(v) for v in items_used_map.values())
    total_qty_requested = sum(item['quantity_requested'] for item in items)
    total_qty_left = total_qty_requested - total_qty_used
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE requests 
            SET installed_part_photo = ?, quantity_used = ?, quantity_left = ?, updated_at = ? 
            WHERE id = ?
        """, (photo_id, total_qty_used, total_qty_left, now, request_id))
        await db.commit()
        
    for item in items:
        used_qty = int(items_used_map.get(str(item['id']), item['quantity_requested']))
        if used_qty > 0:
            await add_or_update_inventory_item(item['item_name'], -used_qty)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    INSERT INTO stock_transactions (item_name, type, quantity, user_id, request_id, created_at)
                    VALUES (?, 'rasxod', ?, ?, ?, ?)
                """, (item['item_name'], used_qty, creator_id, request_id, now))
                await db.commit()

async def update_request_details(request_id: int, description: str, vehicle_name: str, old_part_photo: str, qty_used: int = None, qty_left: int = None, request_type: str = 'repair'):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute("""
            UPDATE requests 
            SET description = ?, vehicle_name = ?, old_part_photo = ?, quantity_used = ?, quantity_left = ?, request_type = ?, status = 'pending_approval', updated_at = ?
            WHERE id = ?
        """, (description, vehicle_name, old_part_photo, qty_used, qty_left, request_type, now, request_id))
        await db.commit()

async def update_request_item(request_id: int, item_name: str, quantity: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE request_items 
            SET item_name = ?, quantity_requested = ?, quantity_missing = ?, quantity_available = 0
            WHERE request_id = ?
        """, (item_name, quantity, quantity, request_id))
        await db.commit()

async def get_requests_by_status(status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.*, u.full_name as creator_name 
            FROM requests r 
            JOIN users u ON r.created_by = u.telegram_id 
            WHERE r.status = ?
            ORDER BY r.id ASC
        """, (status,)) as cursor:
            return await cursor.fetchall()

async def get_all_requests():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.*, u.full_name as creator_name 
            FROM requests r 
            JOIN users u ON r.created_by = u.telegram_id 
            ORDER BY r.id ASC
        """) as cursor:
            return await cursor.fetchall()

async def get_requests_movement():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM (
                SELECT r.*, 
                       u_creator.full_name as creator_name,
                       u_approver.full_name as approver_name,
                       u_wh.full_name as warehouseman_name,
                       u_courier.full_name as courier_name
                FROM requests r
                LEFT JOIN users u_creator ON r.created_by = u_creator.telegram_id
                LEFT JOIN users u_approver ON r.approved_by = u_approver.telegram_id
                LEFT JOIN users u_wh ON r.warehouse_released_by = u_wh.telegram_id
                LEFT JOIN users u_courier ON r.courier_id = u_courier.telegram_id
                ORDER BY r.id DESC
                LIMIT 15
            ) ORDER BY id ASC
        """) as cursor:
            return await cursor.fetchall()

async def get_my_requests(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM requests 
            WHERE created_by = ? AND status NOT IN ('completed', 'rejected')
            ORDER BY id ASC
        """, (telegram_id,)) as cursor:
            return await cursor.fetchall()

# --- INVENTORY & REQUEST_ITEMS MODULI ---

async def get_inventory_item(name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM inventory WHERE name = ?", (name.strip(),)) as cursor:
            return await cursor.fetchone()

async def get_all_inventory():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM inventory ORDER BY name") as cursor:
            return await cursor.fetchall()

async def add_or_update_inventory_item(name: str, quantity_change: int, category: str = 'butlovchi'):
    async with aiosqlite.connect(DB_PATH) as db:
        name_clean = name.strip()
        cursor = await db.execute("SELECT quantity FROM inventory WHERE name = ?", (name_clean,))
        row = await cursor.fetchone()
        if row:
            new_qty = max(0, row[0] + quantity_change)
            await db.execute("UPDATE inventory SET quantity = ? WHERE name = ?", (new_qty, name_clean))
        else:
            await db.execute("INSERT INTO inventory (name, quantity, category) VALUES (?, ?, ?)", (name_clean, max(0, quantity_change), category))
        await db.commit()


async def update_inventory_manually(name: str, new_qty: int, category: str, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        name_clean = name.strip()
        # 1. Oldingi miqdorni aniqlash
        cursor = await db.execute("SELECT quantity FROM inventory WHERE name = ?", (name_clean,))
        row = await cursor.fetchone()
        old_qty = row[0] if row else 0
        
        # 2. Yangilash
        await db.execute("""
            INSERT INTO inventory (name, quantity, category) VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET quantity = excluded.quantity, category = excluded.category
        """, (name_clean, new_qty, category))
        
        # 3. Tranzaksiyani yozish
        diff = new_qty - old_qty
        if diff != 0:
            tx_type = 'prixod' if diff > 0 else 'rasxod'
            now = datetime.datetime.now().isoformat()
            await db.execute("""
                INSERT INTO stock_transactions (item_name, type, quantity, user_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (name_clean, tx_type, abs(diff), user_id, now))
            
        await db.commit()

async def add_request_item(request_id: int, item_name: str, quantity_requested: int, quantity_available: int, quantity_missing: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO request_items (request_id, item_name, quantity_requested, quantity_available, quantity_missing)
            VALUES (?, ?, ?, ?, ?)
        """, (request_id, item_name.strip(), quantity_requested, quantity_available, quantity_missing))
        await db.commit()

async def get_request_items(request_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM request_items WHERE request_id = ?", (request_id,)) as cursor:
            return await cursor.fetchall()

# Skladchik topshiriqni qabul qilganda ombor zaxirasini yangilash
async def update_stock_on_receipt(request_id: int):
    req = await get_request(request_id)
    wh_id = req['warehouse_released_by'] if req else None
    now = datetime.datetime.now().isoformat()
    
    items = await get_request_items(request_id)
    for item in items:
        # Skladchik kuryerdan yetishmagan tovarlarni qabul qildi,
        # shuning uchun zaxiraga yetishmagan (keltirilgan) miqdorni qo'shamiz
        if item['quantity_missing'] > 0:
            await add_or_update_inventory_item(item['item_name'], item['quantity_missing'])
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    INSERT INTO stock_transactions (item_name, type, quantity, user_id, request_id, created_at)
                    VALUES (?, 'prixod', ?, ?, ?, ?)
                """, (item['item_name'], item['quantity_missing'], wh_id, request_id, now))
                await db.commit()

def parse_with_regex_excel(text: str) -> list:
    import re
    items = []
    normalized = text.lower()
    units = ['ta', 'dona', 'shtuk', 'шт', 'шт.', 'd', 'x']
    
    # Try pattern 1: (number) (optional ta/dona) (name)
    pattern1 = r'(\d+)\s*(?:ta|dona|shtuk|шт|шт\.|d|x|\*|-)?\s+([^0-9,;\n]+)'
    matches = re.findall(pattern1, normalized)
    
    if matches:
        for qty_str, name_str in matches:
            name = name_str.strip().strip(',.;- \t')
            if not name or name in units:
                continue
            qty = int(qty_str)
            items.append({'name': name.capitalize(), 'qty': qty})
            
    # If no valid items were found with Pattern 1, try Pattern 2
    if not items:
        pattern2 = r'([^0-9,;\n]+)\s+(\d+)\s*(?:ta|dona|shtuk|шт|d)?'
        matches2 = re.findall(pattern2, normalized)
        if matches2:
            for name_str, qty_str in matches2:
                name = name_str.strip().strip(',.;- \t')
                if not name or name in units:
                    continue
                qty = int(qty_str)
                items.append({'name': name.capitalize(), 'qty': qty})
                
    return items

# Excel formatida barcha zayavkalarni eksport qilish - Chiroyli formatlangan
async def export_requests_to_excel():
    import openpyxl
    from openpyxl.styles import (
        PatternFill, Font, Alignment, Border, Side, GradientFill
    )
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()

    STATUS_LABELS_UZ = {
        'pending_approval': 'Tasdiqlash kutilmoqda',
        'pending_admin_approval': 'Admin kutilmoqda',
        'approved': 'Tasdiqlangan',
        'delivering': "Yo'lda",
        'searching': 'Qidirilmoqda',
        'purchased': 'Sotib olindi',
        'waiting_receipt': 'Qabul kutilmoqda',
        'completed': 'Yakunlandi',
        'rejected': 'Rad etildi',
    }

    # ============================
    # RANGLAR VA USLUBLAR
    # ============================
    COLOR_HEADER_BG    = "1F4E79"   # To'q ko'k
    COLOR_HEADER_FONT  = "FFFFFF"   # Oq
    COLOR_TITLE_BG     = "2E75B6"   # Ko'k
    COLOR_ALT_ROW      = "DEEAF1"   # Och ko'k (juft qatorlar)
    COLOR_BORDER       = "ADB9CA"   # Kulrang chegara

    COLOR_STATUS = {
        'pending_approval': "FFF2CC",  # sariq
        'pending_admin_approval': "FFE699",  # to'qroq sariq
        'approved':         "E2EFDA",  # yashil
        'delivering':       "FCE4D6",  # to'q sariq
        'searching':        "FFF2CC",  # sariq
        'purchased':        "FCE4D6",  # to'q sariq
        'waiting_receipt':  "DDEBF7",  # ko'k
        'completed':        "C6EFCE",  # to'q yashil
        'rejected':         "F4CCCC",  # qizil
    }

    def header_style(cell, text):
        cell.value = text
        cell.font = Font(name='Calibri', bold=True, color=COLOR_HEADER_FONT, size=11)
        cell.fill = PatternFill(fill_type='solid', fgColor=COLOR_HEADER_BG)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = thin_border()

    def thin_border():
        side = Side(style='thin', color=COLOR_BORDER)
        return Border(left=side, right=side, top=side, bottom=side)

    def data_cell(cell, value, row_num, status=None, is_num=False):
        cell.value = value
        cell.font = Font(name='Calibri', size=10)
        cell.alignment = Alignment(horizontal='center' if is_num else 'left',
                                   vertical='center', wrap_text=True)
        cell.border = thin_border()
        if status and status in COLOR_STATUS:
            cell.fill = PatternFill(fill_type='solid', fgColor=COLOR_STATUS[status])
        elif row_num % 2 == 0:
            cell.fill = PatternFill(fill_type='solid', fgColor=COLOR_ALT_ROW)

    # ============================
    # 1-VAROQ: ZAYAVKALAR BATAFSIL
    # ============================
    ws1 = wb.active
    ws1.title = "📋 Zayavkalar"
    ws1.sheet_view.showGridLines = False

    # Sarlavha satri (1-qator)
    ws1.merge_cells('A1:N1')
    title_cell = ws1['A1']
    title_cell.value = "MO BUTLASH — ZAYAVKALAR HISOBOTI"
    title_cell.font = Font(name='Calibri', bold=True, size=14, color=COLOR_HEADER_FONT)
    title_cell.fill = PatternFill(fill_type='solid', fgColor=COLOR_TITLE_BG)
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws1.row_dimensions[1].height = 28

    # Ustun sarlavhalari (2-qator)
    headers_zayavka = [
        ("T/r", 6),
        ("Yaratuvchi (Mexanik/Brigadir)", 28),
        ("Zayavka Tavsifi", 35),
        ("Yaratilgan Vaqt", 18),
        ("Holati", 22),
        ("Boshqaruvchi", 22),
        ("Ta'minotchi", 22),
        ("Skladchik", 22),
        ("Mahsulot Nomi", 28),
        ("So'ralgan (dona)", 16),
        ("Omborda Bor Edi", 16),
        ("Keltirildi / Yetishmagan", 20),
        ("Ishlatildi (dona)", 16),
        ("Omborda Qoldi (dona)", 18),
    ]
    for col_idx, (hdr, width) in enumerate(headers_zayavka, start=1):
        cell = ws1.cell(row=2, column=col_idx)
        header_style(cell, hdr)
        ws1.column_dimensions[get_column_letter(col_idx)].width = width
    ws1.row_dimensions[2].height = 36

    # Ma'lumotlar
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.id, creator.full_name as creator_name, r.description, r.created_at, r.status,
                   manager.full_name as manager_name, courier.full_name as courier_name,
                   warehouse.full_name as warehouseman_name,
                   ri.item_name, ri.quantity_requested, ri.quantity_available, ri.quantity_missing,
                   r.quantity_used, r.quantity_left
            FROM requests r
            LEFT JOIN users creator ON r.created_by = creator.telegram_id
            LEFT JOIN users manager ON r.approved_by = manager.telegram_id
            LEFT JOIN users courier ON r.courier_id = courier.telegram_id
            LEFT JOIN users warehouse ON r.warehouse_released_by = warehouse.telegram_id
            LEFT JOIN request_items ri ON r.id = ri.request_id
            ORDER BY r.id ASC
        """) as cursor:
            rows = await cursor.fetchall()

    processed_rows = []
    for r in rows:
        item_name = r['item_name'] or ""
        parsed = parse_with_regex_excel(item_name)
        if len(parsed) > 1:
            for item in parsed:
                v_row = dict(r)
                v_row['item_name'] = item['name']
                v_row['quantity_requested'] = item['qty']
                v_row['quantity_missing'] = item['qty']
                v_row['quantity_available'] = 0
                v_row['quantity_used'] = item['qty']
                v_row['quantity_left'] = 0
                processed_rows.append(v_row)
        else:
            v_row = dict(r)
            if item_name:
                v_row['item_name'] = item_name.capitalize()
            processed_rows.append(v_row)

    # Zayavkalar bo'yicha ketma-ketlikda guruhlash
    grouped_requests = []
    current_req_id = None
    current_group = []
    
    for r in processed_rows:
        req_id = r['id']
        if req_id != current_req_id:
            if current_group:
                grouped_requests.append(current_group)
            current_group = [r]
            current_req_id = req_id
        else:
            current_group.append(r)
    if current_group:
        grouped_requests.append(current_group)

    column_widths = [width for _, width in headers_zayavka]
    current_row = 3

    for group in grouped_requests:
        num_items = len(group)
        start_row = current_row
        end_row = current_row + num_items - 1
        
        for offset, r in enumerate(group):
            row_idx = current_row + offset
            
            row_vals_item = [
                r['id'],
                r['creator_name'] or "—",
                r['description'] or "—",
                r['created_at'][:16].replace('T', ' ') if r['created_at'] else "—",
                STATUS_LABELS_UZ.get(r['status'], r['status'] or "—"),
                r['manager_name'] or "—",
                r['courier_name'] or "—",
                r['warehouseman_name'] or "—",
                r['item_name'] or "—",
                r['quantity_requested'] or 0,
                r['quantity_available'] or 0,
                r['quantity_missing'] or 0,
                r['quantity_used'] if r['quantity_used'] is not None else "—",
                r['quantity_left'] if r['quantity_left'] is not None else "—",
            ]
            
            status_key = r['status']
            for col_idx, val in enumerate(row_vals_item, start=1):
                cell = ws1.cell(row=row_idx, column=col_idx, value=val)
                is_num = col_idx in (1, 10, 11, 12, 13, 14)
                data_cell(cell, val, row_idx, status_key, is_num)
                
            # Dinamik qator balandligini hisoblash
            max_lines = 1
            for val, width in zip(row_vals_item, column_widths):
                if val is not None and isinstance(val, str):
                    lines = val.count('\n') + 1
                    for part in val.split('\n'):
                        part_len = len(part)
                        effective_width = max(5, width - 2)
                        if part_len > effective_width:
                            lines += (part_len - 1) // effective_width
                    max_lines = max(max_lines, lines)
            ws1.row_dimensions[row_idx].height = max(20, max_lines * 15 + 5)
            
        # Vertikal birlashtirish (T/r, Mexanik, Tavsif, Holat, Boshqaruvchi, Ta'minotchi, Skladchi, Ishlatildi, Qoldi)
        if num_items > 1:
            cols_to_merge = [1, 2, 3, 4, 5, 6, 7, 8, 13, 14]
            for col_idx in cols_to_merge:
                ws1.merge_cells(start_row=start_row, start_column=col_idx, end_row=end_row, end_column=col_idx)
                
                # Birlashgan katak matnlarini vertical center tekislash
                for r_idx in range(start_row, end_row + 1):
                    cell = ws1.cell(row=r_idx, column=col_idx)
                    cell.alignment = Alignment(horizontal='center' if col_idx in (1, 13, 14) else 'left',
                                               vertical='center', wrap_text=True)
                    
        current_row += num_items

    ws1.freeze_panes = "A3"

    # ============================
    # 2-VAROQ: OMBOR QOLDIQLARI
    # ============================
    ws2 = wb.create_sheet(title="📦 Ombor Qoldiqlari")
    ws2.sheet_view.showGridLines = False

    # Sarlavha
    ws2.merge_cells('A1:C1')
    title2 = ws2['A1']
    title2.value = "OMBOR ZAXIRASI — JORIY QOLDIQLAR"
    title2.font = Font(name='Calibri', bold=True, size=13, color=COLOR_HEADER_FONT)
    title2.fill = PatternFill(fill_type='solid', fgColor=COLOR_TITLE_BG)
    title2.alignment = Alignment(horizontal='center', vertical='center')
    ws2.row_dimensions[1].height = 26

    # Ustun sarlavhalari
    inv_headers = [("T/r", 6), ("Mahsulot Nomi", 35), ("Omborda Bor Miqdor (Dona)", 26), ("Turi", 22)]
    for col_idx, (hdr, width) in enumerate(inv_headers, start=1):
        cell = ws2.cell(row=2, column=col_idx)
        header_style(cell, hdr)
        ws2.column_dimensions[get_column_letter(col_idx)].width = width
    ws2.row_dimensions[2].height = 34

    # Inventory ma'lumotlari
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, quantity, category FROM inventory ORDER BY name") as cursor:
            inv_items = await cursor.fetchall()

    # Pre-process inventory items: split and aggregate duplicates
    inventory_summary = {}
    for item in inv_items:
        name = item['name'] or ""
        parsed = parse_with_regex_excel(name)
        category = item['category']
        if len(parsed) > 1:
            for parsed_item in parsed:
                p_name = parsed_item['name']
                p_qty = parsed_item['qty']
                if p_name in inventory_summary:
                    inventory_summary[p_name]['quantity'] += p_qty
                else:
                    inventory_summary[p_name] = {'quantity': p_qty, 'category': category}
        else:
            p_name = name.capitalize()
            p_qty = item['quantity']
            if p_name in inventory_summary:
                inventory_summary[p_name]['quantity'] += p_qty
            else:
                inventory_summary[p_name] = {'quantity': p_qty, 'category': category}

    # Convert to sorted list
    processed_inv_items = []
    for p_name, details in sorted(inventory_summary.items()):
        processed_inv_items.append({
            'name': p_name,
            'quantity': details['quantity'],
            'category': details['category']
        })

    for inv_idx, item in enumerate(processed_inv_items, start=3):
        qty = item['quantity']
        bg = "C6EFCE" if qty > 0 else "F4CCCC"  # yashil = bor, qizil = yo'q
        category_text = "Tayyor mahsulot" if item['category'] == 'tayyor' else "Butlovchi mahsulot"

        num_cell = ws2.cell(row=inv_idx, column=1, value=inv_idx - 2)
        num_cell.font = Font(name='Calibri', size=10, bold=True)
        num_cell.alignment = Alignment(horizontal='center', vertical='center')
        num_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        num_cell.border = thin_border()

        name_cell = ws2.cell(row=inv_idx, column=2, value=item['name'])
        name_cell.font = Font(name='Calibri', size=10)
        name_cell.alignment = Alignment(horizontal='left', vertical='center')
        name_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        name_cell.border = thin_border()

        qty_cell = ws2.cell(row=inv_idx, column=3, value=qty)
        qty_cell.font = Font(name='Calibri', size=11, bold=True)
        qty_cell.alignment = Alignment(horizontal='center', vertical='center')
        qty_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        qty_cell.border = thin_border()

        cat_cell = ws2.cell(row=inv_idx, column=4, value=category_text)
        cat_cell.font = Font(name='Calibri', size=10)
        cat_cell.alignment = Alignment(horizontal='center', vertical='center')
        cat_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        cat_cell.border = thin_border()
        ws2.row_dimensions[inv_idx].height = 20

    ws2.freeze_panes = "A3"

    # ============================
    # 3-VAROQ: KIRIMLAR (PRIXOD)
    # ============================
    ws3 = wb.create_sheet(title="📥 Kirimlar (Prixod)")
    ws3.sheet_view.showGridLines = False

    # Sarlavha
    ws3.merge_cells('A1:F1')
    title3 = ws3['A1']
    title3.value = "OMBORGA KIRIM QILINGAN TOVARLAR (PRIXOD)"
    title3.font = Font(name='Calibri', bold=True, size=13, color=COLOR_HEADER_FONT)
    title3.fill = PatternFill(fill_type='solid', fgColor=COLOR_TITLE_BG)
    title3.alignment = Alignment(horizontal='center', vertical='center')
    ws3.row_dimensions[1].height = 26

    # Ustun sarlavhalari
    tx_headers = [
        ("T/r", 6),
        ("Mahsulot Nomi", 35),
        ("Miqdori (dona)", 18),
        ("Mas'ul Xodim", 28),
        ("Zayavka ID", 15),
        ("Sana / Vaqt", 22)
    ]
    for col_idx, (hdr, width) in enumerate(tx_headers, start=1):
        cell = ws3.cell(row=2, column=col_idx)
        header_style(cell, hdr)
        ws3.column_dimensions[get_column_letter(col_idx)].width = width
    ws3.row_dimensions[2].height = 34

    # Kirimlar ma'lumotlari
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.item_name, t.quantity, u.full_name as user_name, t.request_id, t.created_at
            FROM stock_transactions t
            LEFT JOIN users u ON t.user_id = u.telegram_id
            WHERE t.type = 'prixod'
            ORDER BY t.id DESC
        """) as cursor:
            prixod_rows = await cursor.fetchall()

    processed_prixod_rows = []
    for tx in prixod_rows:
        name = tx['item_name'] or ""
        parsed = parse_with_regex_excel(name)
        if len(parsed) > 1:
            for parsed_item in parsed:
                v_tx = dict(tx)
                v_tx['item_name'] = parsed_item['name']
                v_tx['quantity'] = parsed_item['qty']
                processed_prixod_rows.append(v_tx)
        else:
            v_tx = dict(tx)
            if name:
                v_tx['item_name'] = name.capitalize()
            processed_prixod_rows.append(v_tx)

    for idx, r in enumerate(processed_prixod_rows, start=3):
        # Greenish bg for prixod rows
        bg = "E2EFDA"
        
        num_cell = ws3.cell(row=idx, column=1, value=idx - 2)
        num_cell.font = Font(name='Calibri', size=10, bold=True)
        num_cell.alignment = Alignment(horizontal='center', vertical='center')
        num_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        num_cell.border = thin_border()

        name_cell = ws3.cell(row=idx, column=2, value=r['item_name'])
        name_cell.font = Font(name='Calibri', size=10)
        name_cell.alignment = Alignment(horizontal='left', vertical='center')
        name_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        name_cell.border = thin_border()

        qty_cell = ws3.cell(row=idx, column=3, value=r['quantity'])
        qty_cell.font = Font(name='Calibri', size=10, bold=True)
        qty_cell.alignment = Alignment(horizontal='center', vertical='center')
        qty_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        qty_cell.border = thin_border()

        user_cell = ws3.cell(row=idx, column=4, value=r['user_name'] or "Avtomatik / Tizim")
        user_cell.font = Font(name='Calibri', size=10)
        user_cell.alignment = Alignment(horizontal='left', vertical='center')
        user_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        user_cell.border = thin_border()

        req_cell = ws3.cell(row=idx, column=5, value=r['request_id'] if r['request_id'] else "—")
        req_cell.font = Font(name='Calibri', size=10)
        req_cell.alignment = Alignment(horizontal='center', vertical='center')
        req_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        req_cell.border = thin_border()

        date_cell = ws3.cell(row=idx, column=6, value=r['created_at'][:16].replace('T', ' ') if r['created_at'] else "—")
        date_cell.font = Font(name='Calibri', size=10)
        date_cell.alignment = Alignment(horizontal='center', vertical='center')
        date_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        date_cell.border = thin_border()
        
        ws3.row_dimensions[idx].height = 20

    ws3.freeze_panes = "A3"

    # ============================
    # 4-VAROQ: CHIQIMLAR (RASXOD)
    # ============================
    ws4 = wb.create_sheet(title="📤 Chiqimlar (Rasxod)")
    ws4.sheet_view.showGridLines = False

    # Sarlavha
    ws4.merge_cells('A1:F1')
    title4 = ws4['A1']
    title4.value = "OMBORDAN CHIQARILGAN TOVARLAR (RASXOD)"
    title4.font = Font(name='Calibri', bold=True, size=13, color=COLOR_HEADER_FONT)
    title4.fill = PatternFill(fill_type='solid', fgColor=COLOR_TITLE_BG)
    title4.alignment = Alignment(horizontal='center', vertical='center')
    ws4.row_dimensions[1].height = 26

    for col_idx, (hdr, width) in enumerate(tx_headers, start=1):
        cell = ws4.cell(row=2, column=col_idx)
        header_style(cell, hdr)
        ws4.column_dimensions[get_column_letter(col_idx)].width = width
    ws4.row_dimensions[2].height = 34

    # Chiqimlar ma'lumotlari
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.item_name, t.quantity, u.full_name as user_name, t.request_id, t.created_at
            FROM stock_transactions t
            LEFT JOIN users u ON t.user_id = u.telegram_id
            WHERE t.type = 'rasxod'
            ORDER BY t.id DESC
        """) as cursor:
            rasxod_rows = await cursor.fetchall()

    processed_rasxod_rows = []
    for tx in rasxod_rows:
        name = tx['item_name'] or ""
        parsed = parse_with_regex_excel(name)
        if len(parsed) > 1:
            for parsed_item in parsed:
                v_tx = dict(tx)
                v_tx['item_name'] = parsed_item['name']
                v_tx['quantity'] = parsed_item['qty']
                processed_rasxod_rows.append(v_tx)
        else:
            v_tx = dict(tx)
            if name:
                v_tx['item_name'] = name.capitalize()
            processed_rasxod_rows.append(v_tx)

    for idx, r in enumerate(processed_rasxod_rows, start=3):
        # Orangish bg for rasxod rows
        bg = "FCE4D6"
        
        num_cell = ws4.cell(row=idx, column=1, value=idx - 2)
        num_cell.font = Font(name='Calibri', size=10, bold=True)
        num_cell.alignment = Alignment(horizontal='center', vertical='center')
        num_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        num_cell.border = thin_border()

        name_cell = ws4.cell(row=idx, column=2, value=r['item_name'])
        name_cell.font = Font(name='Calibri', size=10)
        name_cell.alignment = Alignment(horizontal='left', vertical='center')
        name_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        name_cell.border = thin_border()

        qty_cell = ws4.cell(row=idx, column=3, value=r['quantity'])
        qty_cell.font = Font(name='Calibri', size=10, bold=True)
        qty_cell.alignment = Alignment(horizontal='center', vertical='center')
        qty_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        qty_cell.border = thin_border()

        user_cell = ws4.cell(row=idx, column=4, value=r['user_name'] or "Avtomatik / Tizim")
        user_cell.font = Font(name='Calibri', size=10)
        user_cell.alignment = Alignment(horizontal='left', vertical='center')
        user_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        user_cell.border = thin_border()

        req_cell = ws4.cell(row=idx, column=5, value=r['request_id'] if r['request_id'] else "—")
        req_cell.font = Font(name='Calibri', size=10)
        req_cell.alignment = Alignment(horizontal='center', vertical='center')
        req_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        req_cell.border = thin_border()

        date_cell = ws4.cell(row=idx, column=6, value=r['created_at'][:16].replace('T', ' ') if r['created_at'] else "—")
        date_cell.font = Font(name='Calibri', size=10)
        date_cell.alignment = Alignment(horizontal='center', vertical='center')
        date_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        date_cell.border = thin_border()
        
        ws4.row_dimensions[idx].height = 20

    ws4.freeze_panes = "A3"

    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    file_path = f"MO_Butlash_Hisobot_{timestamp}.xlsx"
    wb.save(file_path)
    return file_path


async def export_daily_report_to_excel():
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    import datetime

    wb = openpyxl.Workbook()

    COLOR_HEADER_BG    = "1F4E79"   # To'q ko'k
    COLOR_HEADER_FONT  = "FFFFFF"   # Oq
    COLOR_TITLE_BG     = "2E75B6"   # Ko'k
    COLOR_ALT_ROW      = "DEEAF1"   # Och ko'k
    COLOR_BORDER       = "ADB9CA"   # Kulrang chegara

    def header_style(cell, text):
        cell.value = text
        cell.font = Font(name='Calibri', bold=True, color=COLOR_HEADER_FONT, size=11)
        cell.fill = PatternFill(fill_type='solid', fgColor=COLOR_HEADER_BG)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = thin_border()

    def thin_border():
        side = Side(style='thin', color=COLOR_BORDER)
        return Border(left=side, right=side, top=side, bottom=side)

    today_str = datetime.date.today().isoformat()

    # ============================
    # 1-VAROQ: OMBOR QOLDIQLARI
    # ============================
    ws1 = wb.active
    ws1.title = "📦 Ombor Qoldiqlari"
    ws1.sheet_view.showGridLines = False

    # Sarlavha
    ws1.merge_cells('A1:D1')
    title1 = ws1['A1']
    title1.value = f"OMBOR QOLDIQLARI MONITORI ({today_str})"
    title1.font = Font(name='Calibri', bold=True, size=13, color=COLOR_HEADER_FONT)
    title1.fill = PatternFill(fill_type='solid', fgColor=COLOR_TITLE_BG)
    title1.alignment = Alignment(horizontal='center', vertical='center')
    ws1.row_dimensions[1].height = 26

    # Ustun sarlavhalari
    inv_headers = [("T/r", 6), ("Mahsulot Nomi", 35), ("Omborda Bor Miqdor (Dona)", 26), ("Turi", 22)]
    for col_idx, (hdr, width) in enumerate(inv_headers, start=1):
        cell = ws1.cell(row=2, column=col_idx)
        header_style(cell, hdr)
        ws1.column_dimensions[get_column_letter(col_idx)].width = width
    ws1.row_dimensions[2].height = 34

    # Inventory ma'lumotlari
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, quantity, category FROM inventory ORDER BY name") as cursor:
            inv_items = await cursor.fetchall()

    # Pre-process inventory items: split and aggregate duplicates
    inventory_summary = {}
    for item in inv_items:
        name = item['name'] or ""
        parsed = parse_with_regex_excel(name)
        category = item['category']
        if len(parsed) > 1:
            for parsed_item in parsed:
                p_name = parsed_item['name']
                p_qty = parsed_item['qty']
                if p_name in inventory_summary:
                    inventory_summary[p_name]['quantity'] += p_qty
                else:
                    inventory_summary[p_name] = {'quantity': p_qty, 'category': category}
        else:
            p_name = name.capitalize()
            p_qty = item['quantity']
            if p_name in inventory_summary:
                inventory_summary[p_name]['quantity'] += p_qty
            else:
                inventory_summary[p_name] = {'quantity': p_qty, 'category': category}

    # Convert to sorted list
    processed_inv_items = []
    for p_name, details in sorted(inventory_summary.items()):
        processed_inv_items.append({
            'name': p_name,
            'quantity': details['quantity'],
            'category': details['category']
        })

    for inv_idx, item in enumerate(processed_inv_items, start=3):
        qty = item['quantity']
        bg = "C6EFCE" if qty > 0 else "F4CCCC"  # yashil = bor, qizil = yo'q
        category_text = "Tayyor mahsulot" if item['category'] == 'tayyor' else "Butlovchi mahsulot"

        num_cell = ws1.cell(row=inv_idx, column=1, value=inv_idx - 2)
        num_cell.font = Font(name='Calibri', size=10, bold=True)
        num_cell.alignment = Alignment(horizontal='center', vertical='center')
        num_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        num_cell.border = thin_border()

        name_cell = ws1.cell(row=inv_idx, column=2, value=item['name'])
        name_cell.font = Font(name='Calibri', size=10)
        name_cell.alignment = Alignment(horizontal='left', vertical='center')
        name_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        name_cell.border = thin_border()

        qty_cell = ws1.cell(row=inv_idx, column=3, value=qty)
        qty_cell.font = Font(name='Calibri', size=11, bold=True)
        qty_cell.alignment = Alignment(horizontal='center', vertical='center')
        qty_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        qty_cell.border = thin_border()

        cat_cell = ws1.cell(row=inv_idx, column=4, value=category_text)
        cat_cell.font = Font(name='Calibri', size=10)
        cat_cell.alignment = Alignment(horizontal='center', vertical='center')
        cat_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        cat_cell.border = thin_border()
        ws1.row_dimensions[inv_idx].height = 20

    ws1.freeze_panes = "A3"

    # ============================
    # 2-VAROQ: PRIXOD (BUGUNGI)
    # ============================
    ws2 = wb.create_sheet(title="📥 Bugungi Kirimlar (Prixod)")
    ws2.sheet_view.showGridLines = False

    ws2.merge_cells('A1:F1')
    title2 = ws2['A1']
    title2.value = f"BUGUNGI KIRIM QILINGAN TOVARLAR ({today_str})"
    title2.font = Font(name='Calibri', bold=True, size=13, color=COLOR_HEADER_FONT)
    title2.fill = PatternFill(fill_type='solid', fgColor=COLOR_TITLE_BG)
    title2.alignment = Alignment(horizontal='center', vertical='center')
    ws2.row_dimensions[1].height = 26

    tx_headers = [
        ("T/r", 6),
        ("Mahsulot Nomi", 35),
        ("Miqdori (dona)", 18),
        ("Mas'ul Xodim", 28),
        ("Zayavka ID", 15),
        ("Sana / Vaqt", 22)
    ]
    for col_idx, (hdr, width) in enumerate(tx_headers, start=1):
        cell = ws2.cell(row=2, column=col_idx)
        header_style(cell, hdr)
        ws2.column_dimensions[get_column_letter(col_idx)].width = width
    ws2.row_dimensions[2].height = 34

    # Prixod ma'lumotlari
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.item_name, t.quantity, u.full_name as user_name, t.request_id, t.created_at
            FROM stock_transactions t
            LEFT JOIN users u ON t.user_id = u.telegram_id
            WHERE t.type = 'prixod' AND t.created_at LIKE ?
            ORDER BY t.id DESC
        """, (f"{today_str}%",)) as cursor:
            prixod_rows = await cursor.fetchall()

    processed_prixod_rows = []
    for tx in prixod_rows:
        name = tx['item_name'] or ""
        parsed = parse_with_regex_excel(name)
        if len(parsed) > 1:
            for parsed_item in parsed:
                v_tx = dict(tx)
                v_tx['item_name'] = parsed_item['name']
                v_tx['quantity'] = parsed_item['qty']
                processed_prixod_rows.append(v_tx)
        else:
            v_tx = dict(tx)
            if name:
                v_tx['item_name'] = name.capitalize()
            processed_prixod_rows.append(v_tx)

    for idx, r in enumerate(processed_prixod_rows, start=3):
        bg = "E2EFDA"
        
        num_cell = ws2.cell(row=idx, column=1, value=idx - 2)
        num_cell.font = Font(name='Calibri', size=10, bold=True)
        num_cell.alignment = Alignment(horizontal='center', vertical='center')
        num_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        num_cell.border = thin_border()

        name_cell = ws2.cell(row=idx, column=2, value=r['item_name'])
        name_cell.font = Font(name='Calibri', size=10)
        name_cell.alignment = Alignment(horizontal='left', vertical='center')
        name_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        name_cell.border = thin_border()

        qty_cell = ws2.cell(row=idx, column=3, value=r['quantity'])
        qty_cell.font = Font(name='Calibri', size=10, bold=True)
        qty_cell.alignment = Alignment(horizontal='center', vertical='center')
        qty_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        qty_cell.border = thin_border()

        user_cell = ws2.cell(row=idx, column=4, value=r['user_name'] or "Avtomatik / Tizim")
        user_cell.font = Font(name='Calibri', size=10)
        user_cell.alignment = Alignment(horizontal='left', vertical='center')
        user_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        user_cell.border = thin_border()

        req_cell = ws2.cell(row=idx, column=5, value=r['request_id'] if r['request_id'] else "—")
        req_cell.font = Font(name='Calibri', size=10)
        req_cell.alignment = Alignment(horizontal='center', vertical='center')
        req_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        req_cell.border = thin_border()

        date_cell = ws2.cell(row=idx, column=6, value=r['created_at'][:16].replace('T', ' ') if r['created_at'] else "—")
        date_cell.font = Font(name='Calibri', size=10)
        date_cell.alignment = Alignment(horizontal='center', vertical='center')
        date_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        date_cell.border = thin_border()
        
        ws2.row_dimensions[idx].height = 20

    ws2.freeze_panes = "A3"

    # ============================
    # 3-VAROQ: RASXOD (BUGUNGI)
    # ============================
    ws3 = wb.create_sheet(title="📤 Bugungi Chiqimlar (Rasxod)")
    ws3.sheet_view.showGridLines = False

    ws3.merge_cells('A1:F1')
    title3 = ws3['A1']
    title3.value = f"BUGUNGI CHIQARILGAN TOVARLAR ({today_str})"
    title3.font = Font(name='Calibri', bold=True, size=13, color=COLOR_HEADER_FONT)
    title3.fill = PatternFill(fill_type='solid', fgColor=COLOR_TITLE_BG)
    title3.alignment = Alignment(horizontal='center', vertical='center')
    ws3.row_dimensions[1].height = 26

    for col_idx, (hdr, width) in enumerate(tx_headers, start=1):
        cell = ws3.cell(row=2, column=col_idx)
        header_style(cell, hdr)
        ws3.column_dimensions[get_column_letter(col_idx)].width = width
    ws3.row_dimensions[2].height = 34

    # Rasxod ma'lumotlari
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.item_name, t.quantity, u.full_name as user_name, t.request_id, t.created_at
            FROM stock_transactions t
            LEFT JOIN users u ON t.user_id = u.telegram_id
            WHERE t.type = 'rasxod' AND t.created_at LIKE ?
            ORDER BY t.id DESC
        """, (f"{today_str}%",)) as cursor:
            rasxod_rows = await cursor.fetchall()

    processed_rasxod_rows = []
    for tx in rasxod_rows:
        name = tx['item_name'] or ""
        parsed = parse_with_regex_excel(name)
        if len(parsed) > 1:
            for parsed_item in parsed:
                v_tx = dict(tx)
                v_tx['item_name'] = parsed_item['name']
                v_tx['quantity'] = parsed_item['qty']
                processed_rasxod_rows.append(v_tx)
        else:
            v_tx = dict(tx)
            if name:
                v_tx['item_name'] = name.capitalize()
            processed_rasxod_rows.append(v_tx)

    for idx, r in enumerate(processed_rasxod_rows, start=3):
        bg = "FCE4D6"
        
        num_cell = ws3.cell(row=idx, column=1, value=idx - 2)
        num_cell.font = Font(name='Calibri', size=10, bold=True)
        num_cell.alignment = Alignment(horizontal='center', vertical='center')
        num_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        num_cell.border = thin_border()

        name_cell = ws3.cell(row=idx, column=2, value=r['item_name'])
        name_cell.font = Font(name='Calibri', size=10)
        name_cell.alignment = Alignment(horizontal='left', vertical='center')
        name_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        name_cell.border = thin_border()

        qty_cell = ws3.cell(row=idx, column=3, value=r['quantity'])
        qty_cell.font = Font(name='Calibri', size=10, bold=True)
        qty_cell.alignment = Alignment(horizontal='center', vertical='center')
        qty_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        qty_cell.border = thin_border()

        user_cell = ws3.cell(row=idx, column=4, value=r['user_name'] or "Avtomatik / Tizim")
        user_cell.font = Font(name='Calibri', size=10)
        user_cell.alignment = Alignment(horizontal='left', vertical='center')
        user_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        user_cell.border = thin_border()

        req_cell = ws3.cell(row=idx, column=5, value=r['request_id'] if r['request_id'] else "—")
        req_cell.font = Font(name='Calibri', size=10)
        req_cell.alignment = Alignment(horizontal='center', vertical='center')
        req_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        req_cell.border = thin_border()

        date_cell = ws3.cell(row=idx, column=6, value=r['created_at'][:16].replace('T', ' ') if r['created_at'] else "—")
        date_cell.font = Font(name='Calibri', size=10)
        date_cell.alignment = Alignment(horizontal='center', vertical='center')
        date_cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        date_cell.border = thin_border()
        
        ws3.row_dimensions[idx].height = 20

    ws3.freeze_panes = "A3"

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    file_path = f"MO_Kunlik_Hisobot_{timestamp}.xlsx"
    wb.save(file_path)
    return file_path


async def split_request(original_request_id: int, missing_item_ids: list) -> int:
    """
    Original zayavkadagi topilmagan mahsulotlarni ajratib,
    yangi faol (approved) zayavka yaratadi.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # 1. Asl zayavka ma'lumotlarini olish
        async with db.execute("SELECT * FROM requests WHERE id = ?", (original_request_id,)) as cursor:
            orig = await cursor.fetchone()
            if not orig:
                raise ValueError("Original request not found")
        
        # 2. Yangi zayavka yaratish (courier_id va warehouse_released_by NULL bo'ladi)
        now = datetime.datetime.now().isoformat()
        cursor = await db.execute("""
            INSERT INTO requests (
                created_by, description, status, approved_by, 
                created_at, updated_at, vehicle_name, old_part_photo, request_type
            )
            VALUES (?, ?, 'approved', ?, ?, ?, ?, ?, ?)
        """, (
            orig['created_by'], 
            orig['description'], 
            orig['approved_by'], 
            orig['created_at'], 
            now, 
            orig['vehicle_name'], 
            orig['old_part_photo'], 
            orig['request_type']
        ))
        new_request_id = cursor.lastrowid
        
        # 3. Tanlangan mahsulotlarni yangi zayavkaga o'tkazish
        for item_id in missing_item_ids:
            await db.execute("""
                UPDATE request_items 
                SET request_id = ? 
                WHERE id = ? AND request_id = ?
            """, (new_request_id, item_id, original_request_id))
            
        await db.commit()
        return new_request_id

async def update_request_price(request_id: int, price: int):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute("""
            UPDATE requests 
            SET price = ?, updated_at = ?
            WHERE id = ?
        """, (price, now, request_id))
        await db.commit()



