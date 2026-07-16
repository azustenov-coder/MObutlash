from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import database as db
import re
from handlers.common import (
    get_main_keyboard,
    get_user_main_keyboard,
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
        await message.answer("Ҳозирда қабул қилинадиган (таъминотчи топшираётган) заявкалар йўқ.")
        return
        
    for r in waiting:
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += (
                f"   • <b>{item['item_name']}</b> — Сўралган: {item['quantity_requested']} та | "
                f"Олиб келинди: {item['quantity_missing']} та\n"
            )
            
        text = (
            f"📥 <b>Заявка №{r['id']} (Қабул қилиш)</b>\n"
            f"👤 <b>Механик/Бригадир:</b> {r['creator_name']}\n"
            f"📋 <b>Тавсиф:</b> {r['description']}\n\n"
            f"🔍 <b>Топширилаётган товарлар:</b>\n{items_text}\n"
            f"Текшириб, қабул қилганингиздан сўнг тасдиқланг."
        )
        await message.answer(text, reply_markup=get_wh_receipt_keyboard(r['id']), parse_mode="HTML")

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
        
    if req['status'] != 'waiting_receipt':
        await callback.answer("Ушбу заявка қабул қилиш ҳолатида эмас ёки аллақачон қабул қилинган!", show_alert=True)
        return
        
    await db.update_request_status(request_id, 'ready_for_installation', callback.from_user.id, 'warehouseman')
    await db.update_stock_on_receipt(request_id)
    
    await callback.answer("Юклар қабул қилинди. Механик ўрнатиши кутилмоқда.")
    
    created_date = db.format_datetime(req['created_at'])
    summary = (
        f"📦 <b>Заявка №{request_id} омборга қабул қилинди.</b>\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 <b>Сана:</b> {created_date}\n"
        f"👤 Складчик: {user['full_name']} қабул қилди.\n"
        f"🔧 Механик томонидан ўрнатилиш va yopilish kutilmoqda."
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=None, parse_mode="HTML")
    else:
        await callback.message.edit_text(summary, reply_markup=None, parse_mode="HTML")
    
    try:
        from main import bot
        from handlers.common import get_mechanic_pickup_keyboard
        kb = get_mechanic_pickup_keyboard(request_id)
        await bot.send_message(
            req['created_by'],
            f"🎉 Сизнинг №{request_id}-сонли заявка бўйича сўралgan mahsulotlar omborga qabul qilindi!\n\n"
            f"Iltimos, mahsulotni skladdan olganingizdan so'ng pastdagi <b>Skladdan oldim</b> tugmasini bosing. "
            f"Shundan keyin ombordan rasxod yoziladi va o'rnatish uchun rasm yuborish tugmasi ochiladi.",
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
                f"📥 <b>Заявка №{request_id} омборга қабул қилинди.</b>\n"
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
        "⚙️ <b>Омбор захирасини бошқариш:</b>\n"
        "Маҳсулот номини юборинг (Масалан: 'Podshipnik 120' yoki 'Moy filtri'):",
        parse_mode="HTML"
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
    
    user = await db.get_user(message.from_user.id)
    await db.update_inventory_manually(name, qty, category, user['telegram_id'])
    await state.clear()
    
    cat_lbl = "Тайёр маҳсулот 📦" if category == "tayyor" else "Бутловчи маҳсулот ⚙️"
    await message.answer(
        f"✅ Омбор янгиланди:\n🔹 <b>{name}</b> — {qty} дона ({cat_lbl}) қилиб белгиланди.",
        reply_markup=await get_user_main_keyboard(message.from_user.id, user['role'])
    )


# --- YETKAZIB BERUVCHI OPERATSIYALARI ---

@router.message(F.text.startswith("Yetkazilishi kutilayotganlar") | F.text.startswith("Етказилиши кутилаётганлар"))
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
            f"🚚 <b>Заявка №{r['id']}</b>\n"
            f"👤 <b>Механик/Бригадир:</b> {r['creator_name']}\n"
            f"📋 <b>Тавсиф:</b> {r['description']}\n\n"
            f"🔍 <b>Олиниши керак бўлган товарлар:</b>\n{items_text}\n"
            f"📅 <b>Сана:</b> {db.format_datetime(r['created_at'])}"
        )
        await message.answer(text, reply_markup=get_courier_take_keyboard(r['id']), parse_mode="HTML")

@router.message(F.text.startswith("Qidirilayotgan tovarlar") | F.text.startswith("Қидирилаётган товарлар"))
async def list_missing_items_for_courier(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    rows = await db.get_courier_missing_items(message.from_user.id)
            
    if not rows:
        await message.answer("Ҳозирда қидирилаётган (етишмаётган) товарлар йўқ.")
        return
        
    await message.answer("🔎 <b>Ҳозирда қидирилаётган товарлар рўйхати:</b>", parse_mode="HTML")
    
    groups = {}
    for r in rows:
        req_id = r['request_id']
        if req_id not in groups:
            groups[req_id] = {
                'vehicle': r['vehicle_name'],
                'status': r['status'],
                'request_type': r['request_type'],
                'price': r['price'],
                'items': []
            }
        groups[req_id]['items'].append(f"• <b>{r['item_name']}</b> — {r['quantity_missing']} та")

    for req_id, data in groups.items():
        text = f"🚗 Машина: {data['vehicle']}\n🆔 Заявка №{req_id}\n\nТоварлар:\n"
        text += "\n".join(data['items'])
        
        kb = None
        if data['status'] == 'purchased':
            if data['price'] and data['price'] > 0:
                kb = get_courier_handover_keyboard(req_id)
            else:
                kb = get_courier_price_keyboard(req_id)
        elif data['status'] == 'delivering':
            kb = get_courier_handover_keyboard(req_id)
        elif data['status'] in ('approved', 'searching'):
            kb = get_courier_action_keyboard(req_id, data['request_type'] or 'purchase')
            
        await message.answer(text, parse_mode="HTML", reply_markup=kb)

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
        
        
    if not await db.claim_courier_request(request_id, callback.from_user.id):
        await callback.answer("Bu zayavkani boshqa ta'minotchi qabul qilib bo'lgan.", show_alert=True)
        return
    await callback.answer("Буюртма етказишга қабул қилинди.")
    
    created_date = db.format_datetime(req['created_at'])
    summary = (
        f"🚚 <b>Заявка №{request_id} таъминотчи {user['full_name']} томонидан олиб келинмоқда.</b>\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 <b>Сана:</b> {created_date}\n"
        f"Телефон: {user['phone']}\n\n"
        f"Илтимос, ҳаракатни танланг:"
    )
    request_type = dict(req).get('request_type', 'purchase') if req else 'purchase'
    kb = get_courier_action_keyboard(request_id, request_type)
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(summary, reply_markup=kb, parse_mode="HTML")
        
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


    if not await db.courier_owns_active_request(request_id, callback.from_user.id):
        await callback.answer("Bu zayavka sizga biriktirilmagan yoki jarayoni yakunlangan.", show_alert=True)
        return

    await db.update_request_status(request_id, 'searching', callback.from_user.id, 'courier')
    await callback.answer("Заявка ҳолати 'Қидирилмоқда' га ўзгартирилди.")

    created_date = db.format_datetime(req['created_at'])
    summary = (
        f"🔎 <b>Заявка №{request_id} бўйича маҳсулотлар таъминотчи {user['full_name']} томонидан қидирилмоқда.</b>\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 <b>Сана:</b> {created_date}\n"
        f"Телефон: {user['phone']}\n\n"
        f"Илтимос, ҳаракатни танланг:"
    )
    request_type = dict(req).get('request_type', 'purchase') if req else 'purchase'
    kb = get_courier_action_keyboard(request_id, request_type)
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(summary, reply_markup=kb, parse_mode="HTML")

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


    if not await db.courier_owns_active_request(request_id, callback.from_user.id):
        await callback.answer("Bu zayavka sizga biriktirilmagan yoki jarayoni yakunlangan.", show_alert=True)
        return

    await db.update_request_status(request_id, 'purchased', callback.from_user.id, 'courier')
    await callback.answer("Заявка ҳолати 'Сотиб олинди' га ўзгартирилди.")

    created_date = db.format_datetime(req['created_at'])
    summary = (
        f"🛒 <b>Заявка №{request_id} бўйича маҳсулот таъминотчи {user['full_name']} томонидан сотиб олинди.</b>\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 <b>Сана:</b> {created_date}\n"
        f"Телефон: {user['phone']}\n\n"
        f"💰 <b>Нархини киритиш учун пастдаги тугмани босинг:</b>"
    )
    kb = get_courier_price_keyboard(request_id)
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(summary, reply_markup=kb, parse_mode="HTML")

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
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'courier' or not await db.courier_owns_active_request(request_id, callback.from_user.id):
        await callback.answer("Bu zayavka sizga biriktirilmagan.", show_alert=True)
        return
    await state.update_data(price_request_id=request_id)
    await state.set_state(CourierPriceStates.waiting_for_price)
    
    await callback.message.answer(
        "💰 <b>Олинgan mahsulotning olinish narxini kiriting (so'mda, faqat son yozing):</b>\n"
        "Masalan: <code>150000</code> yoki <code>25000</code>",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(CourierPriceStates.waiting_for_price)
async def process_courier_price_message(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        await state.clear()
        return
    if not message.text:
        await message.answer("Илтимос, narxni son shaklida yozib yuboring:")
        return
        
    clean_text = re.sub(r'[^\d]', '', message.text)
    if not clean_text:
        await message.answer("Илтимос, фақат рақам киритинг (Масалан: <code>150000</code>):", parse_mode="HTML")
        return
        
    try:
        price = int(clean_text)
        if price < 0:
            raise ValueError()
    except ValueError:
        await message.answer("Илтимос, нолдан катта бутун сон киритинг (Масалан: <code>150000</code>):", parse_mode="HTML")
        return
        
    state_data = await state.get_data()
    request_id = state_data.get('price_request_id')

    if not request_id or not await db.courier_owns_active_request(request_id, message.from_user.id):
        await state.clear()
        await message.answer("Bu zayavka sizga biriktirilmagan yoki jarayoni yakunlangan.")
        return
    
    await db.update_request_price(request_id, price)
    await state.clear()
    
    req = await db.get_request(request_id)
    if not req:
        await message.answer("Заявка топилмади.")
        return
        
    created_date = db.format_datetime(req['created_at'])
    formatted_price = f"{price:,}".replace(",", " ")
    
    summary = (
        f"🛒 <b>Заявка №{request_id} бўйича маҳсулот таъминотчи {user['full_name']} томонидан сотиб олинди ва йўлда.</b>\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"💰 <b>Нархи:</b> {formatted_price} сўм\n"
        f"📅 <b>Сана:</b> {created_date}\n"
        f"Телефон: {user['phone']}\n\n"
        f"Энди маҳсулотни омборга топширганингиздан сўнг пастдаги тугмани босинг:"
    )
    
    await message.answer(
        summary,
        reply_markup=get_courier_handover_keyboard(request_id),
        parse_mode="HTML"
    )
    await message.answer(
        "Asosiy menyu qayta ko'rsatildi.",
        reply_markup=await get_user_main_keyboard(message.from_user.id, user['role']),
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
        
        
    if not await db.courier_owns_active_request(request_id, callback.from_user.id):
        await callback.answer("Bu zayavka sizga biriktirilmagan yoki jarayoni yakunlangan.", show_alert=True)
        return

    if req['status'] in ('waiting_receipt', 'ready_for_installation', 'completed'):
        await callback.answer("Буюртма аллақачон топширилган!", show_alert=True)
        return
        
    await db.update_request_status(request_id, 'waiting_receipt', callback.from_user.id, 'courier')
    await callback.answer("Топширилди деб белгиланди. Складчик тасдиқлаши кутилмоқда.")
    
    created_date = db.format_datetime(req['created_at'])
    summary = (
        f"📦 <b>Заявка №{request_id} складга олиб келинди.</b>\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 <b>Сана:</b> {created_date}\n"
        f"👤 Таъминотчи {user['full_name']} топширди. Складчик қабул қилиши кутилмоқда."
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=None, parse_mode="HTML")
    else:
        await callback.message.edit_text(summary, reply_markup=None, parse_mode="HTML")

    await callback.message.answer(
        "Asosiy menyu yangilandi.",
        reply_markup=await get_user_main_keyboard(callback.from_user.id, user['role']),
    )
        
    warehousemen = await db.get_users_by_role('warehouseman')
    for wh in warehousemen:
        try:
            from main import bot
            msg_text = (
                f"📥 <b>Таъминотчи {user['full_name']} заявка №{request_id} бўйича юкларни олиб келди!</b>\n\n"
                f"👤 Механик/Бригадир: {req['creator_name']}\n"
                f"📋 Тавсиф: {req['description']}\n"
                f"📅 <b>Сана:</b> {created_date}\n\n"
                f"Қабул қилиб олиш ва тасдиқлаш учун пастдаги тугмани босинг."
            )
            kb = get_wh_receipt_keyboard(request_id)
            if req['old_part_photo']:
                await bot.send_photo(
                    wh['telegram_id'],
                    photo=req['old_part_photo'],
                    caption=msg_text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    wh['telegram_id'],
                    text=msg_text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
        except Exception as e:
            print(f"Skladchikni ogohlantirishda xato: {e}")

@router.message(
    F.text.startswith("Sklad qabulini kutayotganlar")
    | F.text.startswith("Склад қабулини кутаётганлар")
)
async def list_courier_waiting_receipts(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        return

    requests = await db.get_courier_waiting_receipts(message.from_user.id)
    if not requests:
        await message.answer("Hozir sklad qabulini kutayotgan zayavkalaringiz yo'q.")
        return

    for req in requests:
        items = await db.get_request_items(req['id'])
        items_text = "\n".join(
            f"• {item['item_name']} — {item['quantity_missing']} ta" for item in items
        ) or "• Mahsulotlar kiritilmagan"
        await message.answer(
            f"📦 <b>Zayavka №{req['id']}</b> skladga topshirilgan.\n"
            f"👤 Buyurtmachi: {req['creator_name']}\n"
            f"📋 Tavsif: {req['description']}\n"
            f"⏳ Holat: skladchik qabul qilishi kutilmoqda\n\n"
            f"<b>Mahsulotlar:</b>\n{items_text}",
            parse_mode="HTML",
        )


@router.message(F.text.startswith("Kun yakuni") | F.text.startswith("Кун якуни"))
async def show_courier_day_summary(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    import datetime
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_pattern = f"{today}%"
    
    delivered_rows, open_count = await db.get_courier_day_summary(
        message.from_user.id, today_pattern
    )
            
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
                
            handover_time = db.format_datetime(row['updated_at'])[-5:]
            
            delivered_text += (
                f"{idx}. 🆔 <b>Заявка №{row['id']}</b>\n"
                f"   🚗 Машина: {row['vehicle_name']}\n"
                f"   📦 Товар: {row['item_name']} ({row['quantity_requested']} та)\n"
                f"   💰 Нархи: {price_text}\n"
                f"   📅 Вақт: {handover_time}\n\n"
            )
    else:
        delivered_text = "<i>(Бугун топширилган заявкалар мавжуд эмас)</i>\n\n"
        
    formatted_total = f"{total_spent:,} сўм".replace(",", " ")
    
    text = (
        f"📊 <b>Кун якуни бўйича етказувчи ҳисоботи:</b>\n"
        f"👤 <b>Таъминотчи:</b> {user['full_name']}\n"
        f"📅 <b>Сана:</b> {today}\n\n"
        f"✅ <b>Бугун топширилган заявкалар:</b>\n\n"
        f"{delivered_text}"
        f"-----------------------------------\n"
        f"💰 <b>Бугунги умумий харажат:</b> {formatted_total}\n"
        f"⏳ <b>Ҳозирда фаол (топширилмаган) заявкалар:</b> {open_count} та"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text.startswith("Aktiv yetkazuvlarim") | F.text.startswith("Актив етказувларим"))
async def list_active_courier_deliveries(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'courier':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    active_reqs = await db.get_courier_active_requests(message.from_user.id)
            
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
            f"🛣️ <b>Фаол заявка №{r['id']}</b>\n"
            f"⚙️ <b>Ҳолати:</b> {status_label}{formatted_price}\n"
            f"👤 <b>Механик/Бригадир:</b> {r['creator_name']}\n"
            f"📋 <b>Тавсиф:</b> {r['description']}\n\n"
            f"🔍 <b>Товарлар:</b>\n{items_text}\n"
            f"📅 <b>Сана:</b> {db.format_datetime(r['created_at'])}"
        )
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
