import aiosqlite
import datetime
from config import DB_PATH

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

async def create_request(created_by: int, description: str):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        cursor = await db.execute("""
            INSERT INTO requests (created_by, description, status, created_at, updated_at)
            VALUES (?, ?, 'pending_approval', ?, ?)
        """, (created_by, description, now, now))
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

async def get_requests_by_status(status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.*, u.full_name as creator_name 
            FROM requests r 
            JOIN users u ON r.created_by = u.telegram_id 
            WHERE r.status = ?
            ORDER BY r.id DESC
        """, (status,)) as cursor:
            return await cursor.fetchall()

async def get_all_requests():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.*, u.full_name as creator_name 
            FROM requests r 
            JOIN users u ON r.created_by = u.telegram_id 
            ORDER BY r.id DESC
        """) as cursor:
            return await cursor.fetchall()

async def get_my_requests(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM requests 
            WHERE created_by = ? 
            ORDER BY id DESC
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

async def add_or_update_inventory_item(name: str, quantity_change: int):
    async with aiosqlite.connect(DB_PATH) as db:
        name_clean = name.strip()
        cursor = await db.execute("SELECT quantity FROM inventory WHERE name = ?", (name_clean,))
        row = await cursor.fetchone()
        if row:
            new_qty = max(0, row[0] + quantity_change)
            await db.execute("UPDATE inventory SET quantity = ? WHERE name = ?", (new_qty, name_clean))
        else:
            await db.execute("INSERT INTO inventory (name, quantity) VALUES (?, ?)", (name_clean, max(0, quantity_change)))
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
    items = await get_request_items(request_id)
    for item in items:
        # Skladchik kuryerdan yetishmagan tovarlarni qabul qildi,
        # shuning uchun zaxiraga yetishmagan (keltirilgan) miqdorni qo'shamiz
        if item['quantity_missing'] > 0:
            await add_or_update_inventory_item(item['item_name'], item['quantity_missing'])

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
    ws1.merge_cells('A1:L1')
    title_cell = ws1['A1']
    title_cell.value = "MO BUTLASH — ZAYAVKALAR HISOBOTI"
    title_cell.font = Font(name='Calibri', bold=True, size=14, color=COLOR_HEADER_FONT)
    title_cell.fill = PatternFill(fill_type='solid', fgColor=COLOR_TITLE_BG)
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws1.row_dimensions[1].height = 28

    # Ustun sarlavhalari (2-qator)
    headers_zayavka = [
        ("№", 6),
        ("Yaratuvchi (Mexanik/Brigadir)", 28),
        ("Zayavka Tavsifi", 35),
        ("Yaratilgan Vaqt", 18),
        ("Holati", 22),
        ("Boshqaruvchi", 22),
        ("Kuryer", 22),
        ("Skladchik", 22),
        ("Mahsulot Nomi", 28),
        ("So'ralgan (dona)", 16),
        ("Omborda Bor Edi", 16),
        ("Keltirildi / Yetishmagan", 20),
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
                   ri.item_name, ri.quantity_requested, ri.quantity_available, ri.quantity_missing
            FROM requests r
            LEFT JOIN users creator ON r.created_by = creator.telegram_id
            LEFT JOIN users manager ON r.approved_by = manager.telegram_id
            LEFT JOIN users courier ON r.courier_id = courier.telegram_id
            LEFT JOIN users warehouse ON r.warehouse_released_by = warehouse.telegram_id
            LEFT JOIN request_items ri ON r.id = ri.request_id
            ORDER BY r.id DESC
        """) as cursor:
            rows = await cursor.fetchall()

    row_vals = [
        [
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
        ]
        for r in rows
    ]

    column_widths = [width for _, width in headers_zayavka]
    for data_row_idx, row_vals_item in enumerate(row_vals, start=3):
        status_key = rows[data_row_idx - 3]['status']
        for col_idx, val in enumerate(row_vals_item, start=1):
            cell = ws1.cell(row=data_row_idx, column=col_idx, value=val)
            is_num = col_idx in (1, 10, 11, 12)
            data_cell(cell, val, data_row_idx, status_key, is_num)
            
        # Dinamik qator balandligini hisoblash (matn uzunligiga qarab)
        max_lines = 1
        for val, width in zip(row_vals_item, column_widths):
            if val is not None and isinstance(val, str):
                # Yangi qator belgilarini hisoblash
                lines = val.count('\n') + 1
                # Uzun satrlarning qatorga bo'linishini hisoblash
                for part in val.split('\n'):
                    part_len = len(part)
                    effective_width = max(5, width - 2)
                    if part_len > effective_width:
                        lines += (part_len - 1) // effective_width
                max_lines = max(max_lines, lines)
                
        ws1.row_dimensions[data_row_idx].height = max(20, max_lines * 15 + 5)

    # Freeze panes: 1-qator va 2-qatorni muzlatish
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
    inv_headers = [("№", 6), ("Mahsulot Nomi", 35), ("Omborda Bor Miqdor (Dona)", 26)]
    for col_idx, (hdr, width) in enumerate(inv_headers, start=1):
        cell = ws2.cell(row=2, column=col_idx)
        header_style(cell, hdr)
        ws2.column_dimensions[get_column_letter(col_idx)].width = width
    ws2.row_dimensions[2].height = 34

    # Inventory ma'lumotlari
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, quantity FROM inventory ORDER BY name") as cursor:
            inv_items = await cursor.fetchall()

    for inv_idx, item in enumerate(inv_items, start=3):
        qty = item['quantity']
        bg = "C6EFCE" if qty > 0 else "F4CCCC"  # yashil = bor, qizil = yo'q

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
        ws2.row_dimensions[inv_idx].height = 20

    ws2.freeze_panes = "A3"

    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    file_path = f"MO_Butlash_Hisobot_{timestamp}.xlsx"
    wb.save(file_path)
    return file_path


