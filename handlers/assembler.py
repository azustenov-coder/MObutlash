from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import aiosqlite
import database as db
import re
from handlers.common import (
    get_main_keyboard,
    get_wh_receipt_keyboard,
    get_courier_take_keyboard,
    get_courier_handover_keyboard,
    get_courier_action_keyboard
)

router = Router()

class StockManagementStates(StatesGroup):
    waiting_for_item_name = State()
    waiting_for_item_category = State()
    waiting_for_item_qty = State()

class CourierPriceStates(StatesGroup):
    waiting_for_price = State()

def get_courier_price_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Нархини киритиш", callback_data=f"cour_price_input_{request_id}")]
    ])

# --- SKLADCHIK OPERATSIYALARI ---

@router.message(F.text.in_(["Tayyorlanishi kutilayotganlar 📦", "Тайёрланиши кутилаётганлар 📦"]))
async def list_incoming_receipts(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'warehouseman':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    waiting = await db.get_requests_by_status('waiting_receipt')
    if not waiting:
        await message.answer("Ҳозирда қабул қилинадиган (таъминотчи топшираётgan) zayavkalar yo'q.")
        return
        
    for r in waiting:
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += (
                f"   • **{item['item_name']}** — Сўралган: {item['quantity_requested']} та | "
                f"Олиб келинди: {item['quantity_missing']} та\n"
            )
            
        text = (
            f"📥 **Заявка №{r['id']} (Қабул қилиш)**\n"
            f"👤 **Механик/Бригадир:** {r['creator_name']}\n"
            f"📋 **Тавсиф:** {r['description']}\n\n"
            f"🔍 **Топширилаётган товарлар:**\n{items_text}\n"
            f"Текшириб, қабул қилганингиздан сўнг тасдиқланг."
        )
        await message.answer(text, reply_markup=get_wh_receipt_keyboard(r['id']), parse_mode="Markdown")

@router.callback_query(F.data.startswith("wh_receipt_confirm_"))
async def process_wh_receipt_confirm(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'warehouseman':
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[3])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Заявка топилмади.")
        await callback.message.delete()
        return
        
    await db.update_request_status(request_id, 'ready_for_installation', callback.from_user.id, 'warehouseman')
    await db.update_stock_on_receipt(request_id)
    
    await callback.answer("Юклар қабул қилинди. Механик ўрнатиши кутилмоқда.")
    
    created_date = req['created_at'][:16].replace('T', ' ')
    summary = (
        f"📦 **Заявка №{request_id} омборга қабул қилинди.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 **Сана:** {created_date}\n"
        f"👤 Складчик: {user['full_name']} қабул қилди.\n"
        f"🔧 Механик томонидан ўрнатилиш va yopilish kutilmoqda."
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=None, parse_mode="Markdown")
    else:
        await callback.message.edit_text(summary, reply_markup=None, parse_mode="Markdown")
    
    try:
        from main import bot
        from handlers.common import get_mechanic_install_keyboard
        kb = get_mechanic_install_keyboard(request_id)
        await bot.send_message(
            req['created_by'],
            f"🎉 Сизнинг №{request_id}-сонли заявка бўйича сўралgan mahsulotlar omborga qabul qilindi!\n\n"
            f"Iltimos, yukni ombordan olib, tegishli joyiga o'rnatganingizdan so'ng isbot sifatida rasm yuboring. "
            f"Bunining uchun quyidagi tugmani bosing.",
            reply_markup=kb
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")
        
    managers = await db.get_users_by_role('manager')
    super_admins = await db.get_users_by_role('super_admin')
    all_admins = list(managers) + list(super_admins)
    for m in all_admins:
        try:
            from main import bot
            await bot.send_message(
                m['telegram_id'],
                f"📥 **Заявка №{request_id} омборга қабул қилинди.**\n"
                f"👤 Механик {req['creator_name']} томонидан ўрнатилиши ва расм юбориб тасдиқланиши кутилмоқда."
            )
        except Exception as e:
            print(f"Boshqaruvchini ogohlantirishda xato: {e}")

@router.message(F.text.in_(["Ombor zaxirasini boshqarish ⚙️", "Омбор захирасини бошқариш ⚙️"]))
async def start_stock_management(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'warehouseman':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    await message.answer(
        "⚙️ **Омбор захирасини бошқариш:**\n"
        "Маҳсулот номини юборинг (Масалан: 'Podshipnik 120' yoki 'Moy filtri'):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(StockManagementStates.waiting_for_item_name)

@router.message(StockManagementStates.waiting_for_item_name)
async def process_stock_name(message: Message, state: FSMContext):
    await state.update_data(stock_name=message.text)
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    cat_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Тайёр маҳсулот 📦"), KeyboardButton(text="Бутловчи маҳсулот ⚙️")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(
        f"Гуруҳни танланг:\n🔹 '{message.text}' қайси тоифага киради?",
        reply_markup=cat_kb
    )
    await state.set_state(StockManagementStates.waiting_for_item_category)

@router.message(StockManagementStates.waiting_for_item_category)
async def process_stock_category(message: Message, state: FSMContext):
    val = message.text
    if val not in ["Тайёр маҳсулот 📦", "Бутловчи маҳсулот ⚙️"]:
        await message.answer("Илтимос, пастдаги тугмалардан биrini tanlang:")
        return
        
    category = "tayyor" if "Тайёр" in val else "butlovchi"
    await state.update_data(stock_category=category)
    
    await message.answer(
        f"🔢 Омборда неча дона бор? (Миқдорини киритинг):",
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
        await message.answer("Илтимос, бутун мусбат сон ёзинг:")
        return
        
    data = await state.get_data()
    name = data['stock_name']
    category = data['stock_category']
    
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute("""
            INSERT INTO inventory (name, quantity, category) VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET quantity = excluded.quantity, category = excluded.category
        """, (name.strip(), qty, category))
        await db_conn.commit()
        
    user = await db.get_user(message.from_user.id)
    await state.clear()
    
    cat_lbl = "Тайёр маҳсулот 📦" if category == "tayyor" else "Бутловчи маҳсулот ⚙️"
    await message.answer(
        f"✅ Омбор янгиланди:\n🔹 **{name}** — {qty} дона ({cat_lbl}) қилиб белгиланди.",
        reply_markup=get_main_keyboard(user['role'])
    )


# --- YETKAZIB BERUVCHI OPERATSIYALARI ---

@router.message(F.text.in_(["Yetkazilishi kutilayotganlar 🚚", "Етказилиши кутилаётганлар 🚚"]))
async def list_approved_to_deliver(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    approved = await db.get_requests_by_status('approved')
    if not approved:
        await message.answer("Ҳозирда етказилиши кутилаётган (тасдиқланган) заявкалар йўқ.")
        return
        
    for r in approved:
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += f"   • {item['item_name']}: {item['quantity_requested']} та (Олиниши керак: {item['quantity_missing']} та)\n"
            
        text = (
            f"🚚 **Заявка №{r['id']}**\n"
            f"👤 **Механик/Бригадир:** {r['creator_name']}\n"
            f"📋 **Тавсиф:** {r['description']}\n\n"
            f"🔍 **Олиниши керак бўлган товарлар:**\n{items_text}\n"
            f"📅 **Сана:** {r['created_at'][:16].replace('T', ' ')}"
        )
        await message.answer(text, reply_markup=get_courier_take_keyboard(r['id']), parse_mode="Markdown")

@router.message(F.text.in_(["Qidirilayotgan tovarlar 🔎", "Қидирилаётган товарлар 🔎"]))
async def list_missing_items_for_courier(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("""
            SELECT r.id as request_id, r.vehicle_name, ri.item_name, ri.quantity_missing
            FROM request_items ri
            JOIN requests r ON ri.request_id = r.id
            WHERE r.status IN ('approved', 'delivering', 'searching') AND ri.quantity_missing > 0
            ORDER BY r.id ASC
        """) as cursor:
            rows = await cursor.fetchall()
            
    if not rows:
        await message.answer("Ҳозирда қидирилаётган (етишмаётган) товарлар йўқ.")
        return
        
    text = "🔎 **Ҳозирда қидирилаётган (сотиб олиниши керак бўлган) товарлар рўйхати:**\n\n"
    for r in rows:
        text += (
            f"• **{r['item_name']}** — {r['quantity_missing']} та\n"
            f"  🚗 Машина: {r['vehicle_name']} | 🆔 Заявка №{r['request_id']}\n\n"
        )
        
    await message.answer(text, parse_mode="Markdown")

@router.callback_query(F.data.startswith("cour_take_"))
async def process_courier_take(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'courier':
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Заявка топилмади.")
        await callback.message.delete()
        return
        
    await db.update_request_status(request_id, 'delivering', callback.from_user.id, 'courier')
    await callback.answer("Буюртма етказишга қабул қилинди.")
    
    created_date = req['created_at'][:16].replace('T', ' ')
    summary = (
        f"🚚 **Заявка №{request_id} таъминотчи {user['full_name']} томонидан олиб келинмоқда.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 **Сана:** {created_date}\n"
        f"Телефон: {user['phone']}\n\n"
        f"Илтимос, ҳаракатни танланг:"
    )
    request_type = dict(req).get('request_type', 'purchase') if 'req' in locals() else dict(r).get('request_type', 'purchase')
    kb = get_courier_action_keyboard(request_id, request_type)
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=kb, parse_mode="Markdown")
    else:
        await callback.message.edit_text(summary, reply_markup=kb, parse_mode="Markdown")
        
    try:
        from main import bot
        await bot.send_message(
            req['created_by'],
            f"🚚 Таъминотчи {user['full_name']} ({user['phone']}) сизнинг №{request_id}-сонли заявкангиздаги маҳсулотларни олиб келиш учун йўлга чиқди."
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")

@router.callback_query(F.data.startswith("cour_search_"))
async def process_courier_search(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'courier':
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Заявка топилмади.")
        await callback.message.delete()
        return

    await db.update_request_status(request_id, 'searching', callback.from_user.id, 'courier')
    await callback.answer("Заявка ҳолати 'Қидирилмоқда' га ўзгартирилди.")

    created_date = req['created_at'][:16].replace('T', ' ')
    summary = (
        f"🔎 **Заявка №{request_id} бўйича маҳсулотлар таъминотчи {user['full_name']} томонидан қидирилмоқда.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 **Сана:** {created_date}\n"
        f"Телефон: {user['phone']}\n\n"
        f"Илтимос, ҳаракатни танланг:"
    )
    request_type = dict(req).get('request_type', 'purchase') if 'req' in locals() else dict(r).get('request_type', 'purchase')
    kb = get_courier_action_keyboard(request_id, request_type)
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=kb, parse_mode="Markdown")
    else:
        await callback.message.edit_text(summary, reply_markup=kb, parse_mode="Markdown")

    try:
        from main import bot
        await bot.send_message(
            req['created_by'],
            f"🔎 Таъминотчи {user['full_name']} ({user['phone']}) сизнинг №{request_id}-сонли заявкангиздаги маҳсулотларни қидиришни бошлади."
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")

@router.callback_query(F.data.startswith("cour_buy_"))
async def process_courier_buy(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'courier':
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Заявка топилмади.")
        await callback.message.delete()
        return

    await db.update_request_status(request_id, 'purchased', callback.from_user.id, 'courier')
    await callback.answer("Заявка ҳолати 'Сотиб олинди' га ўзгартирилди.")

    created_date = req['created_at'][:16].replace('T', ' ')
    summary = (
        f"🛒 **Заявка №{request_id} бўйича маҳсулот таъминотчи {user['full_name']} томонидан сотиб олинди.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 **Сана:** {created_date}\n"
        f"Телефон: {user['phone']}\n\n"
        f"💰 **Нархини киритиш учун пастдаги тугмани босинг:**"
    )
    kb = get_courier_price_keyboard(request_id)
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=kb, parse_mode="Markdown")
    else:
        await callback.message.edit_text(summary, reply_markup=kb, parse_mode="Markdown")

    try:
        from main import bot
        await bot.send_message(
            req['created_by'],
            f"🛒 Таъминотчи {user['full_name']} ({user['phone']}) сизнинг №{request_id}-сонли заявкангиздаги маҳсулотларни сотиб олди ва олиб келмоқда."
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")

@router.callback_query(F.data.startswith("cour_price_input_"))
async def process_courier_price_input_callback(callback: CallbackQuery, state: FSMContext):
    request_id = int(callback.data.split("_")[3])
    await state.update_data(price_request_id=request_id)
    await state.set_state(CourierPriceStates.waiting_for_price)
    
    await callback.message.answer(
        "💰 **Олинgan mahsulotning olinish narxini kiriting (so'mda, faqat son yozing):**\n"
        "Masalan: `150000` yoki `25000`",
        reply_markup=ReplyKeyboardRemove()
    )
    await callback.answer()

@router.message(CourierPriceStates.waiting_for_price)
async def process_courier_price_message(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not message.text:
        await message.answer("Илтимос, narxni son shaklida yozib yuboring:")
        return
        
    clean_text = re.sub(r'[\s,\._-]', '', message.text.strip())
    try:
        price = int(clean_text)
        if price < 0:
            raise ValueError()
    except ValueError:
        await message.answer("Илтимос, нолдан катта бутун сон киритинг (Масалан: `150000`):")
        return
        
    state_data = await state.get_data()
    request_id = state_data.get('price_request_id')
    
    await db.update_request_price(request_id, price)
    await state.clear()
    
    req = await db.get_request(request_id)
    if not req:
        await message.answer("Заявка топилмади.")
        return
        
    created_date = req['created_at'][:16].replace('T', ' ')
    formatted_price = f"{price:,}".replace(",", " ")
    
    summary = (
        f"🛒 **Заявка №{request_id} бўйича маҳсулот таъминотчи {user['full_name']} томонидан сотиб олинди ва йўлда.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"💰 **Нархи:** {formatted_price} сўм\n"
        f"📅 **Сана:** {created_date}\n"
        f"Телефон: {user['phone']}\n\n"
        f"Энди маҳсулотни омборга топширганингиздан сўнг пастдаги тугмани босинг:"
    )
    
    await message.answer(
        summary,
        reply_markup=get_courier_handover_keyboard(request_id),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("cour_handover_"))
async def process_courier_handover(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'courier':
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Заявка топилмади.")
        await callback.message.delete()
        return
        
    await db.update_request_status(request_id, 'waiting_receipt', callback.from_user.id, 'courier')
    await callback.answer("Топширилди деб белгиланди. Складчик тасдиқлаши кутилмоқда.")
    
    created_date = req['created_at'][:16].replace('T', ' ')
    summary = (
        f"📦 **Заявка №{request_id} складга олиб келинди.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 **Сана:** {created_date}\n"
        f"👤 Таъминотчи {user['full_name']} топширди. Складчик қабул қилиши кутилмоқда."
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=None, parse_mode="Markdown")
    else:
        await callback.message.edit_text(summary, reply_markup=None, parse_mode="Markdown")
        
    warehousemen = await db.get_users_by_role('warehouseman')
    for wh in warehousemen:
        try:
            from main import bot
            msg_text = (
                f"📥 **Таъминотчи {user['full_name']} заявка №{request_id} бўйича юкларни олиб келди!**\n\n"
                f"👤 Механик/Бригадир: {req['creator_name']}\n"
                f"📋 Тавсиф: {req['description']}\n"
                f"📅 **Сана:** {created_date}\n\n"
                f"Қабул қилиб олиш ва тасдиқлаш учун пастдаги тугмани босинг."
            )
            kb = get_wh_receipt_keyboard(request_id)
            if req['old_part_photo']:
                await bot.send_photo(
                    wh['telegram_id'],
                    photo=req['old_part_photo'],
                    caption=msg_text,
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
            else:
                await bot.send_message(
                    wh['telegram_id'],
                    text=msg_text,
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
        except Exception as e:
            print(f"Skladchikni ogohlantirishda xato: {e}")

@router.message(F.text.in_(["Kun yakuni 📊", "Кун якуни 📊"]))
async def show_courier_day_summary(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    import datetime
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_pattern = f"{today}%"
    
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        # Get list of requests delivered today (waiting_receipt, ready_for_installation, completed)
        async with conn.execute("""
            SELECT r.id, r.vehicle_name, r.price, r.updated_at, ri.item_name, ri.quantity_requested
            FROM requests r
            JOIN request_items ri ON ri.request_id = r.id
            WHERE r.courier_id = ? 
              AND r.status IN ('waiting_receipt', 'ready_for_installation', 'completed') 
              AND r.updated_at LIKE ?
            ORDER BY r.updated_at ASC
        """, (message.from_user.id, today_pattern)) as cursor:
            delivered_rows = await cursor.fetchall()
            
        # Count open/delivering/searching/purchased
        async with conn.execute("""
            SELECT COUNT(*) FROM requests
            WHERE courier_id = ? AND status IN ('delivering', 'searching', 'purchased')
        """, (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            open_count = row[0] if row else 0
            
    delivered_text = ""
    total_spent = 0
    
    if delivered_rows:
        for idx, row in enumerate(delivered_rows, start=1):
            price_val = row['price'] or 0
            total_spent += price_val
            
            if price_val > 0:
                price_text = f"{price_val:,} сўм".replace(",", " ")
            else:
                price_text = "Таъмирлаш (Нархсиз)"
                
            handover_time = row['updated_at'][11:16]  # Just HH:MM
            
            delivered_text += (
                f"{idx}. 🆔 **Заявка №{row['id']}**\n"
                f"   🚗 Машина: {row['vehicle_name']}\n"
                f"   📦 Товар: {row['item_name']} ({row['quantity_requested']} та)\n"
                f"   💰 Нархи: {price_text}\n"
                f"   📅 Вақт: {handover_time}\n\n"
            )
    else:
        delivered_text = "*(Бугун топширилган заявкалар мавжуд эмас)*\n\n"
        
    formatted_total = f"{total_spent:,} сўм".replace(",", " ")
    
    text = (
        f"📊 **Кун якуни бўйича етказувчи ҳисоботи:**\n"
        f"👤 **Таъминотчи:** {user['full_name']}\n"
        f"📅 **Сана:** {today}\n\n"
        f"✅ **Бугун топширилган заявкалар:**\n\n"
        f"{delivered_text}"
        f"-----------------------------------\n"
        f"💰 **Бугунги умумий харажат:** {formatted_total}\n"
        f"⏳ **Ҳозирда фаол (топширилмаган) заявкалар:** {open_count} та"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text.in_(["Aktiv yetkazuvlarim 🛣️", "Актив етказувларим 🛣️"]))
async def list_active_courier_deliveries(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("""
            SELECT r.*, u.full_name as creator_name
            FROM requests r
            JOIN users u ON r.created_by = u.telegram_id
            WHERE r.courier_id = ? AND r.status IN ('delivering', 'searching', 'purchased')
            ORDER BY r.id ASC
        """, (message.from_user.id,)) as cursor:
            active_reqs = await cursor.fetchall()
            
    if not active_reqs:
        await message.answer("Сизда ҳозирда фаол (йўлдаги) етказувлар мавжуд эмас.")
        return
        
    status_labels = {
        'delivering': 'Йўлда 🚚',
        'searching': 'Қидирилмоқда 🔎',
        'purchased': 'Сотиб олинди 🛒'
    }
        
    for r in active_reqs:
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += f"   • {item['item_name']}: {item['quantity_requested']} та (Олиниши керак: {item['quantity_missing']} та)\n"
            
        status_label = status_labels.get(r['status'], r['status'])
        
        # Differentiate keyboard actions for purchase requests (forces price entry)
        if r['status'] == 'purchased':
            if r['price'] and r['price'] > 0:
                kb = get_courier_handover_keyboard(r['id'])
                formatted_price = f" ({r['price']:,} сўм)".replace(",", " ")
            else:
                kb = get_courier_price_keyboard(r['id'])
                formatted_price = " (Нархи киритилмаган)"
        else:
            kb = get_courier_action_keyboard(r['id'], dict(r).get('request_type', 'purchase'))
            formatted_price = ""
            
        text = (
            f"🛣️ **Фаол заявка №{r['id']}**\n"
            f"⚙️ **Ҳолати:** {status_label}{formatted_price}\n"
            f"👤 **Механик/Бригадир:** {r['creator_name']}\n"
            f"📋 **Тавсиф:** {r['description']}\n\n"
            f"🔍 **Товарлар:**\n{items_text}\n"
            f"📅 **Сана:** {r['created_at'][:16].replace('T', ' ')}"
        )
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
