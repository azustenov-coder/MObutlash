from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import database as db
from handlers.common import get_main_keyboard

router = Router()

class StockManagementStates(StatesGroup):
    waiting_for_item_name = State()
    waiting_for_item_qty = State()

# --- INTERFEYS TUGMALARI ---

# Skladchik qabul qilishi uchun tugma
def get_wh_receipt_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Yuklarni qabul qildim va Tasdiqlayman ✅", callback_data=f"wh_receipt_confirm_{request_id}")]
    ])

# Yetkazib beruvchi yukni olish tugmasi
def get_courier_take_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Yetkazib berishni boshlash 🚚", callback_data=f"cour_take_{request_id}")]
    ])

# Yetkazib beruvchi topshirish tugmasi
def get_courier_handover_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Skladchikka topshirish 📦", callback_data=f"cour_handover_{request_id}")]
    ])


# --- SKLADCHIK OPERATSIYALARI ---

# Tayyorlanishi (Qabul qilinishi) kutilayotgan zayavkalar
@router.message(F.text == "Tayyorlanishi kutilayotganlar 📦")
async def list_incoming_receipts(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'warehouseman':
        await message.answer("Sizda ushbu komandani bajarish uchun huquq yo'q.")
        return
        
    # Kuryer olib kelgan va skladchi tasdiqlashi kutilayotgan zayavkalar
    waiting = await db.get_requests_by_status('waiting_receipt')
    if not waiting:
        await message.answer("Hozirda qabul qilinadigan (kuryer topshirayotgan) zayavkalar yo'q.")
        return
        
    for r in waiting:
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += (
                f"   • **{item['item_name']}** — So'ralgan: {item['quantity_requested']} ta | "
                f"Olib kelindi (Yetishmagan): {item['quantity_missing']} ta\n"
            )
            
        text = (
            f"📥 **Zayavka №{r['id']} (Qabul qilish)**\n"
            f"👤 **Mexanik/Brigadir:** {r['creator_name']}\n"
            f"📋 **Tavsif:** {r['description']}\n\n"
            f"🔍 **Topshirilayotgan tovarlar:**\n{items_text}\n"
            f"Tekshirib, qabul qilganingizdan so'ng tasdiqlang."
        )
        await message.answer(text, reply_markup=get_wh_receipt_keyboard(r['id']), parse_mode="Markdown")

@router.callback_query(F.data.startswith("wh_receipt_confirm_"))
async def process_wh_receipt_confirm(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'warehouseman':
        await callback.answer("Sizda ushbu operatsiyani bajarish huquqi yo'q!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[3])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Zayavka topilmadi.")
        await callback.message.delete()
        return
        
    # Bazani va stocklarni yangilaymiz (Zaxiraga qo'shish)
    await db.update_request_status(request_id, 'completed', callback.from_user.id, 'warehouseman')
    await db.update_stock_on_receipt(request_id)
    
    await callback.answer("Zayavka qabul qilindi va yakunlandi.")
    
    items = await db.get_request_items(request_id)
    items_text = ""
    for item in items:
        items_text += f"   • {item['item_name']}: +{item['quantity_missing']} ta omborga qo'shildi\n"
        
    await callback.message.edit_text(
        f"✅ **Zayavka №{request_id} qabul qilindi va yakunlandi.**\n"
        f"📋 Tavsif: {req['description']}\n"
        f"👤 Skladchik: {user['full_name']}\n\n"
        f"📈 **Ombor zaxirasi yangilandi:**\n{items_text}",
        reply_markup=None,
        parse_mode="Markdown"
    )
    
    # Yaratuvchini (Mexanik/Brigadir) ogohlantirish
    try:
        from main import bot
        await bot.send_message(
            req['created_by'],
            f"🎉 Sizning №{request_id}-sonli zayavka bo'yicha so'ralgan mahsulotlar omborga qabul qilindi va butlandi!"
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")
        
    # Boshqaruvchini ogohlantirish
    managers = await db.get_users_by_role('manager')
    for m in managers:
        try:
            from main import bot
            await bot.send_message(
                m['telegram_id'],
                f"✅ **Zayavka №{request_id} yakunlandi.**\n"
                f"👤 Kuryer topshirdi, Skladchik {user['full_name']} qabul qilib oldi."
            )
        except Exception as e:
            print(f"Boshqaruvchini ogohlantirishda xato: {e}")

# Sklad zaxiralarini qo'shish / boshqarish menyusi
@router.message(F.text == "Ombor zaxirasini boshqarish ⚙️")
async def start_stock_management(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'warehouseman':
        await message.answer("Sizda ushbu komandani bajarish uchun huquq yo'q.")
        return
        
    await message.answer(
        "⚙️ **Ombor zaxirasini boshqarish:**\n"
        "Mahsulot nomini yuboring (Masalan: 'Podshipnik 120' yoki 'Moy filtri'):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(StockManagementStates.waiting_for_item_name)

@router.message(StockManagementStates.waiting_for_item_name)
async def process_stock_name(message: Message, state: FSMContext):
    await state.update_data(stock_name=message.text)
    await message.answer(
        f"🔢 '{message.text}' dan omborda necha dona bor? (Miqdorini kiriting):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(StockManagementStates.waiting_for_item_qty)

@router.message(StockManagementStates.waiting_for_item_qty)
async def process_stock_qty(message: Message, state: FSMContext):
    try:
        qty = int(message.text)
        if qty < 0:
            raise ValueError()
    except ValueError:
        await message.answer("Iltimos, butun musbat son yozing:")
        return
        
    data = await state.get_data()
    name = data['stock_name']
    
    # Ombordagi qoldiqni yangilash yoki qo'shish
    # Bu yerda add_or_update_inventory_item ishlatamiz, lekin yangi qiymat to'g'ridan-to'g'ri yozilsin desak, bazadagi qiymatni o'rniga yozishimiz kerak.
    # Keling, database.py dagi add_or_update_inventory_item o'rniga to'g'ridan-to'g'ri o'rnatadigan funksiya yaratamiz yoki bazadan farqini hisoblab yuboramiz.
    # Yoki database.py da to'g'ridan-to'g'ri o'rnatishni yozamiz.
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute("""
            INSERT INTO inventory (name, quantity) VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET quantity = excluded.quantity
        """, (name.strip(), qty))
        await db_conn.commit()
        
    user = await db.get_user(message.from_user.id)
    await state.clear()
    
    await message.answer(
        f"✅ Ombor yangilandi:\n🔹 **{name}** — {qty} dona qilib belgilandi.",
        reply_markup=get_main_keyboard(user['role'])
    )


# --- YETKAZIB BERUVCHI OPERATSIYALARI ---

# Yetkazilishi kutilayotgan zayavkalar (Boshqaruvchi tasdiqlagan)
@router.message(F.text == "Yetkazilishi kutilayotganlar 🚚")
async def list_approved_to_deliver(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        await message.answer("Sizda ushbu komandani bajarish uchun huquq yo'q.")
        return
        
    approved = await db.get_requests_by_status('approved')
    if not approved:
        await message.answer("Hozirda yetkazilishi kutilayotgan (tasdiqlangan) zayavkalar yo'q.")
        return
        
    for r in approved:
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += f"   • {item['item_name']}: {item['quantity_requested']} ta (Olinishi kerak: {item['quantity_missing']} ta)\n"
            
        text = (
            f"🚚 **Zayavka №{r['id']}**\n"
            f"👤 **Mexanik/Brigadir:** {r['creator_name']}\n"
            f"📋 **Tavsif:** {r['description']}\n\n"
            f"🔍 **Olinishi kerak bo'lgan tovarlar:**\n{items_text}\n"
            f"📅 **Sana:** {r['created_at'][:19].replace('T', ' ')}"
        )
        await message.answer(text, reply_markup=get_courier_take_keyboard(r['id']), parse_mode="Markdown")

@router.callback_query(F.data.startswith("cour_take_"))
async def process_courier_take(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'courier':
        await callback.answer("Sizda ushbu operatsiyani bajarish huquqi yo'q!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Zayavka topilmadi.")
        await callback.message.delete()
        return
        
    # Statusni 'delivering' (yo'lda) ga o'zgartirish
    await db.update_request_status(request_id, 'delivering', callback.from_user.id, 'courier')
    await callback.answer("Buyurtma yetkazishga qabul qilindi.")
    
    await callback.message.edit_text(
        f"🚚 **Zayavka №{request_id} kuryer {user['full_name']} tomonidan olib kelinmoqda.**\n"
        f"📋 Tavsif: {req['description']}\n"
        f"Telefon: {user['phone']}",
        reply_markup=None,
        parse_mode="Markdown"
    )
    
    # Yaratuvchini ogohlantirish
    try:
        from main import bot
        await bot.send_message(
            req['created_by'],
            f"🚚 Yetkazib beruvchi {user['full_name']} ({user['phone']}) sizning №{request_id}-sonli zayavkangizdagi mahsulotlarni olib kelish uchun yo'lga chiqdi."
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")

# Aktiv yetkazuvlarim ro'yxati
@router.message(F.text == "Aktiv yetkazuvlarim 🛣️")
async def list_courier_active(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        await message.answer("Sizda ushbu komandani bajarish uchun huquq yo'q.")
        return
        
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute("""
            SELECT r.*, u.full_name as creator_name 
            FROM requests r 
            JOIN users u ON r.created_by = u.telegram_id 
            WHERE r.courier_id = ? AND r.status = 'delivering'
        """, (message.from_user.id,)) as cursor:
            active = await cursor.fetchall()
            
    if not active:
        await message.answer("Sizda hozirda faol yetkazib berishlar yo'q.")
        return
        
    for r in active:
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += f"   • {item['item_name']}: {item['quantity_requested']} ta (Olib kelingan: {item['quantity_missing']} ta)\n"
            
        text = (
            f"🛣️ **Zayavka №{r['id']}**\n"
            f"👤 **Mexanik/Brigadir:** {r['creator_name']}\n"
            f"📋 **Tavsif:** {r['description']}\n\n"
            f"🔍 **Tarkib:**\n{items_text}\n"
            f"Yukni skladchiga topshirganingizdan keyin pastdagi tugmani bosing."
        )
        await message.answer(text, reply_markup=get_courier_handover_keyboard(r['id']), parse_mode="Markdown")

@router.callback_query(F.data.startswith("cour_handover_"))
async def process_courier_handover(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'courier':
        await callback.answer("Sizda ushbu operatsiyani bajarish huquqi yo'q!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Zayavka topilmadi.")
        await callback.message.delete()
        return
        
    # Statusni 'waiting_receipt' (sklad qabul qilishi kutilmoqda) ga o'zgartirish
    await db.update_request_status(request_id, 'waiting_receipt', callback.from_user.id, 'courier')
    await callback.answer("Topshirildi deb belgilandi. Skladchik tasdiqlashi kutilmoqda.")
    
    await callback.message.edit_text(
        f"📦 **Zayavka №{request_id} skladga olib kelindi.**\n"
        f"📋 Tavsif: {req['description']}\n"
        f"👤 Kuryer {user['full_name']} topshirdi. Skladchik qabul qilishi kutilmoqda.",
        reply_markup=None,
        parse_mode="Markdown"
    )
    
    # Skladchiklarni ogohlantirish
    warehousemen = await db.get_users_by_role('warehouseman')
    for wh in warehousemen:
        try:
            from main import bot
            await bot.send_message(
                wh['telegram_id'],
                f"📥 **Kuryer {user['full_name']} zayavka №{request_id} bo'yicha yuklarni olib keldi!**\n\n"
                f"👤 Mexanik/Brigadir: {req['creator_name']}\n"
                f"📋 Tavsif: {req['description']}\n"
                f"Qabul qilib olish va tasdiqlash uchun skladchi menyusiga kiring."
            )
        except Exception as e:
            print(f"Skladchikni ogohlantirishda xato: {e}")
