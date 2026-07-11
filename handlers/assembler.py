from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import database as db
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


# --- SKLADCHIK OPERATSIYALARI ---

# Tayyorlanishi (Qabul qilinishi) kutilayotgan zayavkalar
@router.message(F.text.in_(["Tayyorlanishi kutilayotganlar 📦", "Тайёрланиши кутилаётганлар 📦"]))
async def list_incoming_receipts(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'warehouseman':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    # Kuryer olib kelgan va skladchi tasdiqlashi kutilayotgan zayavkalar
    waiting = await db.get_requests_by_status('waiting_receipt')
    if not waiting:
        await message.answer("Ҳозирда қабул қилинадиган (таъминотчи топшираётган) заявкалар йўқ.")
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
        
    # Bazani va stocklarni yangilaymiz (Zaxiraga qo'shish)
    await db.update_request_status(request_id, 'ready_for_installation', callback.from_user.id, 'warehouseman')
    await db.update_stock_on_receipt(request_id)
    
    await callback.answer("Юклар қабул қилинди. Механик ўрнатиши кутилмоқда.")
    
    items = await db.get_request_items(request_id)
    items_text = ""
    for item in items:
        items_text += f"   • {item['item_name']}: +{item['quantity_missing']} та омборга қўшилди\n"
        
    created_date = req['created_at'][:16].replace('T', ' ')
    summary = (
        f"📦 **Заявка №{request_id} омборга қабул қилинди.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 **Сана:** {created_date}\n"
        f"👤 Складчик: {user['full_name']} қабул қилди.\n"
        f"🔧 Механик томонидан ўрнатилиш ва ёпилиш кутилмоқда."
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=summary,
            reply_markup=None,
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            summary,
            reply_markup=None,
            parse_mode="Markdown"
        )
    
    # Yaratuvchini (Mexanik/Brigadir) ogohlantirish
    try:
        from main import bot
        from handlers.common import get_mechanic_install_keyboard
        kb = get_mechanic_install_keyboard(request_id)
        await bot.send_message(
            req['created_by'],
            f"🎉 Сизнинг №{request_id}-сонли заявка бўйича сўралган маҳсулотлар омборга қабул қилинди!\n\n"
            f"Илтимос, юкни омбордан олиб, тегишли жойига ўрнатганингиздан сўнг исбот сифатида расм юборинг. "
            f"Бунинг учун қуйидаги тугмани босинг.",
            reply_markup=kb
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")
        
    # Boshqaruvchini ogohlantirish
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

# Sklad zaxiralarini qo'shish / boshqarish menyusi
@router.message(F.text.in_(["Ombor zaxirasini boshqarish ⚙️", "Омбор захирасини бошқариш ⚙️"]))
async def start_stock_management(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'warehouseman':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    await message.answer(
        "⚙️ **Омбор захирасини бошқариш:**\n"
        "Маҳсулот номини юборинг (Масалан: 'Подшипник 120' ёки 'Мой фильтри'):",
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
        await message.answer("Илтимос, пастдаги тугмалардан бирини танланг:")
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

# Yetkazilishi kutilayotgan zayavkalar (Boshqaruvchi tasdiqlagan)
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
        
    # Statusni 'delivering' (yo'lda) ga o'zgartirish
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
    kb = get_courier_action_keyboard(request_id)
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=summary,
            reply_markup=kb,
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            summary,
            reply_markup=kb,
            parse_mode="Markdown"
        )
        
    # Yaratuvchini ogohlantirish
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

    # Statusni 'searching' ga o'zgartirish
    await db.update_request_status(request_id, 'searching', callback.from_user.id, 'courier')
    await callback.answer("Заявка ҳолати 'Қидирилмоқда' га ўзгартирилdi.")

    created_date = req['created_at'][:16].replace('T', ' ')
    summary = (
        f"🔎 **Заявка №{request_id} бўйича маҳсулотлар таъминотчи {user['full_name']} томонидан қидирилмоқда.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 **Сана:** {created_date}\n"
        f"Телефон: {user['phone']}\n\n"
        f"Илтимос, ҳаракатни танланг:"
    )
    kb = get_courier_action_keyboard(request_id)
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=kb, parse_mode="Markdown")
    else:
        await callback.message.edit_text(summary, reply_markup=kb, parse_mode="Markdown")

    # Yaratuvchini ogohlantirish
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

    # Statusni 'purchased' ga o'zgartirish
    await db.update_request_status(request_id, 'purchased', callback.from_user.id, 'courier')
    await callback.answer("Заявка ҳолати 'Сотиб олинди' га ўзгартирилди.")

    created_date = req['created_at'][:16].replace('T', ' ')
    summary = (
        f"🛒 **Заявка №{request_id} бўйича маҳсулотлар таъминотчи {user['full_name']} томонидан сотиб олинди ва йўлда.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 **Сана:** {created_date}\n"
        f"Телефон: {user['phone']}\n\n"
        f"Илтимос, ҳаракатни танланг:"
    )
    kb = get_courier_action_keyboard(request_id)
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=kb, parse_mode="Markdown")
    else:
        await callback.message.edit_text(summary, reply_markup=kb, parse_mode="Markdown")

    # Yaratuvchini ogohlantirish
    try:
        from main import bot
        await bot.send_message(
            req['created_by'],
            f"🛒 Таъминотчи {user['full_name']} ({user['phone']}) сизнинг №{request_id}-сонли заявкангиздаги маҳсулотларни сотиб олди ва олиб келмоқда."
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")

# Aktiv yetkazuvlarim ro'yxati
@router.message(F.text.in_(["Aktiv yetkazuvlarim 🛣️", "Актив етказувларим 🛣️"]))
async def list_courier_active(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute("""
            SELECT r.*, u.full_name as creator_name 
            FROM requests r 
            JOIN users u ON r.created_by = u.telegram_id 
            WHERE r.courier_id = ? AND r.status IN ('delivering', 'searching', 'purchased')
        """, (message.from_user.id,)) as cursor:
            active = await cursor.fetchall()
            
    if not active:
        await message.answer("Сизда ҳозирда фаол етказиб беришлар йўқ.")
        return
        
    for r in active:
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += f"   • {item['item_name']}: {item['quantity_requested']} та (Олиб келинган: {item['quantity_missing']} та)\n"
            
        text = (
            f"🛣️ **Заявка №{r['id']}**\n"
            f"👤 **Механик/Бригадир:** {r['creator_name']}\n"
            f"📋 **Тавсиф:** {r['description']}\n\n"
            f"🔍 **Таркиб:**\n{items_text}\n"
            f"Юкни складчига топширганингиздан кейин пастдаги тугмани босинг."
        )
        await message.answer(text, reply_markup=get_courier_action_keyboard(r['id']), parse_mode="Markdown")

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
        
    # Statusni 'waiting_receipt' (sklad qabul qilishi kutilmoqda) ga o'zgartirish
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
        await callback.message.edit_caption(
            caption=summary,
            reply_markup=None,
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            summary,
            reply_markup=None,
            parse_mode="Markdown"
        )
        
    # Skladchiklarni ogohlantirish (bilan birga rasm va inline tugma ham yuboriladi)
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
