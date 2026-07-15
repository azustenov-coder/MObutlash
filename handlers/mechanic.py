from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import database as db
import re
from handlers.common import get_main_keyboard, get_user_main_keyboard, get_request_manage_keyboard, get_mechanic_install_keyboard, get_mechanic_pickup_keyboard, refresh_vehicle_cache
from handlers.controller import STATUS_LABELS, send_installation_photo

router = Router()

class RequestCreationStates(StatesGroup):
    waiting_for_vehicle = State()
    waiting_for_photo = State()
    waiting_for_requester = State()
    waiting_for_request_type = State()
    waiting_for_items_text = State()
    waiting_for_loop_decision = State()
    waiting_for_manual_item_type = State()
    waiting_for_manual_item_name = State()
    waiting_for_manual_item_qty = State()
    waiting_for_breakdown_reason = State()

class RequestInstallationStates(StatesGroup):
    waiting_for_installation_photo = State()
    waiting_for_qty_used = State()

# Helper to generate vehicles inline keyboard grid
def get_vehicles_inline_keyboard(vehicles_list, list_type: str = "all"):
    keyboard = []
    row = []
    for veh in vehicles_list:
        keyboard_button = InlineKeyboardButton(text=veh, callback_data=f"veh_info_{veh}_{list_type}")
        row.append(keyboard_button)
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Local request parser
async def parse_request_text(text: str) -> list:
    return parse_with_regex(text)

def parse_with_regex(text: str) -> list:
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
            itype = 'purchase'
            if any(word in name for word in ['ta\'mirlash', 'tamirlash', 'remont', 'sozlash', 'tuzatish']):
                itype = 'repair'
            items.append({'type': itype, 'name': name, 'qty': qty})
            
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
                itype = 'purchase'
                if any(word in name for word in ['ta\'mirlash', 'tamirlash', 'remont', 'sozlash', 'tuzatish']):
                    itype = 'repair'
                items.append({'type': itype, 'name': name, 'qty': qty})
                
    if not items:
        clean_text = normalized.strip().strip(',.;- \t')
        if clean_text:
            itype = 'purchase'
            if any(word in clean_text for word in ['ta\'mirlash', 'tamirlash', 'remont', 'sozlash', 'tuzatish']):
                itype = 'repair'
            items.append({'type': itype, 'name': clean_text, 'qty': 1})
            
    return items

@router.message(F.text.startswith("Соз ҳолат 🟢") | F.text.in_(["Soz avtolar 🟢", "Соз автолар 🟢", "Соз ҳолат 🟢"]))
async def show_healthy_vehicles(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier', 'manager', 'super_admin', 'observer']:
        await message.answer("Сизда ушбу командани бажариш uchun huquq yo'q.")
        return
        
    healthy = await db.get_healthy_vehicles()
    if not healthy:
        await message.answer("Тизимда соз avtolar topilmadi.")
        return
        
    await message.answer(
        "🟢 **Соз ҳолатдаги автолар рўйхати:**\n"
        "Тафсилотлар ва тарихни кўриш uchun mashinani tanlang:",
        reply_markup=get_vehicles_inline_keyboard(healthy, "soz"),
        parse_mode="Markdown"
    )

@router.message(F.text.startswith("Носоз ҳолат 🔴") | F.text.in_(["Nosoz avtolar 🔴", "Носоз автолар 🔴", "Носоз ҳолат 🔴"]))
async def show_broken_vehicles(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier', 'manager', 'super_admin', 'observer']:
        await message.answer("Сизда ушбу командани бажариш uchun huquq yo'q.")
        return
        
    broken = await db.get_broken_vehicles()
    if not broken:
        await message.answer("Тизимда носоз (таъмирланаётган) автолар топилмади.")
        return
        
    await message.answer(
        "🔴 **Носоз ҳолатдаги (таъмирланаётган) автолар рўйхати:**\n"
        "Тафсилотлар ва фаол заявкаларни кўриш учун машинани танланг:",
        reply_markup=get_vehicles_inline_keyboard(broken, "nosoz"),
        parse_mode="Markdown"
    )

@router.message(
    F.text.in_(["Avtolar 🚗", "Автолар 🚗", "Avtomashinalar 🚗", "Автомашиналар 🚗"])
    | F.text.startswith("Avtolar 🚗")
    | F.text.startswith("Автолар 🚗")
    | F.text.startswith("Avtomashinalar 🚗")
    | F.text.startswith("Автомашиналар 🚗")
)
async def show_all_vehicles(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier', 'super_admin', 'manager', 'observer']:
        await message.answer("Сизда ушбу командани бажариш uchun huquq yo'q.")
        return
        
    vehicles = await db.get_all_vehicles()
    if not vehicles:
        await message.answer("Тизимда бирорта ҳам автоулов топилмади.")
        return

    # The reply keyboard is rebuilt from PostgreSQL so a newly added vehicle is reflected immediately.
    await refresh_vehicle_cache()
    await message.answer(
        f"🚗 Автомашиналар сони: <b>{len(vehicles)}</b>",
        reply_markup=await get_user_main_keyboard(message.from_user.id, user['role']),
        parse_mode="HTML",
    )
        
    await message.answer(
        "🚗 **Тизимдаги барча автолар рўйхати:**\n"
        "Ҳолати ва тафсилотларни кўриш учун машинани танланг:",
        reply_markup=get_vehicles_inline_keyboard(vehicles, "all"),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("veh_info_"))
async def process_vehicle_info(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    user_role = user['role'] if user else None
    
    parts = callback.data.split("_")
    vehicle_name = parts[2]
    list_type = parts[3] if len(parts) > 3 else "all"
    
    active_requests, history_requests, vehicle = await db.get_vehicle_overview(vehicle_name)
    veh_status = vehicle['status'] if vehicle else 'soz'
    veh_reason = vehicle['reason'] if vehicle else None
            
    status_emoji = "🔴 Носоз ҳолат" if veh_status == 'nosoz' else "🟢 Соз ҳолат"
    
    text = (
        f"🚗 <b>Автомобил рақами:</b> {vehicle_name}\n\n"
        f"👤 <b>Ҳайдовчи:</b> {vehicle.get('driver_name') or 'Киритилмаган'}\n\n"
        f"📞 <b>Телефон:</b> {vehicle.get('driver_phone') or 'Киритилмаган'}\n\n"
        f"🚙 <b>Машина номи:</b> {vehicle.get('vehicle_model') or 'Киритилмаган'}\n\n"
        f"⚙️ <b>Ҳолати:</b> {status_emoji}\n"
    )
    if veh_status == 'nosoz' and veh_reason:
        text += f"\n💬 <b>Сабаби:</b> {veh_reason}\n"
    text += "\n"
    
    if active_requests:
        text += "⚠️ <b>Фаол бузилишлар ва заявкалар:</b>\n"
        for r in active_requests:
            created_date = db.format_datetime(r['created_at'])
            status_label = STATUS_LABELS.get(r['status'], r['status'])
            text += (
                f"   • 🆔 <b>Заявка №{r['id']}</b> ({status_label})\n"
                f"     Тавсиф: {r['description']}\n"
                f"     Сана: {created_date}\n\n"
            )
    else:
        text += "✅ <i>Ушбу машинани таъмирлаш бўйича заявка мавжуд эмас.</i>\n\n"
        
    if history_requests:
        text += "📋 <b>Охирги таъмирлаш тарихи (максимум 5 та):</b>\n"
        for r in history_requests:
            closed_date = db.format_datetime(r['updated_at'])
            status_label = STATUS_LABELS.get(r['status'], r['status'])
            text += f"   • Заявка №{r['id']} — {r['description']} ({status_label}, {closed_date})\n"
            
    buttons = []
    if user_role in ['mechanic', 'brigadier']:
        buttons.append([
            InlineKeyboardButton(text="🟢 Соз ҳолат", callback_data=f"veh_setstatus_{vehicle_name}_soz"),
            InlineKeyboardButton(text="🔴 Носоз ҳолат", callback_data=f"veh_setstatus_{vehicle_name}_nosoz")
        ])
        buttons.append([InlineKeyboardButton(text="✍️ Ушбу машина учун заявка очиш", callback_data=f"veh_newreq_{vehicle_name}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Орқага", callback_data=f"veh_list_back_{list_type}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("veh_setstatus_"))
async def process_veh_setstatus(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier', 'manager', 'super_admin', 'observer']:
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ!", show_alert=True)
        return
        
    parts = callback.data.split("_")
    vehicle_name = parts[2]
    new_status = parts[3]
    
    if new_status == 'soz':
        await db.update_vehicle_status(vehicle_name, 'soz', None)
        await callback.answer(f"✅ {vehicle_name} ҳолати ўзгартирилди: СОЗ", show_alert=True)
        
        healthy = await db.get_healthy_vehicles()
        if not healthy:
            await callback.message.edit_text("Тизимда соз автолар топилмаdi.", reply_markup=None)
            return
            
        await callback.message.edit_text(
            "🟢 <b>Соз ҳолатдаги avtolar ro'yxati:</b>\n"
            "Тафсилотлар ва тарихни кўриш uchun mashinani tanlang:",
            reply_markup=get_vehicles_inline_keyboard(healthy, "soz"),
            parse_mode="HTML"
        )
    else:
        await state.clear()
        await state.update_data(status_vehicle_name=vehicle_name)
        await state.set_state(RequestCreationStates.waiting_for_breakdown_reason)
        
        cancel_kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="Бекор қилиш ❌")]
        ], resize_keyboard=True, one_time_keyboard=True)
        
        await callback.message.answer(
            f"🔴 <b>{vehicle_name}</b> ни Носоз deb belgilash sababini (nosozlikni) yozing:\n"
            f"(Масалан: 'Моторда ортиқча шовқин бор' ёки 'Ходовой қисмида муаммо')",
            reply_markup=cancel_kb,
            parse_mode="HTML"
        )
        await callback.answer()

@router.message(RequestCreationStates.waiting_for_breakdown_reason)
async def process_breakdown_reason(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    text = message.text.strip()
    
    if text == "Бекор қилиш ❌":
        await state.clear()
        await message.answer("Ҳолатни ўзгартириш бекор қилинди.", reply_markup=get_main_keyboard(user['role']))
        return
        
    state_data = await state.get_data()
    vehicle_name = state_data.get('status_vehicle_name')
    
    if not vehicle_name:
        await state.clear()
        await message.answer("Хатолик юз берди. Илтимос, қайтадан уриниб кўринг.", reply_markup=get_main_keyboard(user['role']))
        return
        
    await db.update_vehicle_status(vehicle_name, 'nosoz', text)
    await state.clear()
    
    await message.answer(
        f"✅ <b>{vehicle_name}</b> ҳолати муваффақиятли НОСОЗ деб белгиланди!\n"
        f"💬 <b>Носозлик сабаби:</b> {text}",
        reply_markup=get_main_keyboard(user['role']),
        parse_mode="HTML"
    )
    
    broken = await db.get_broken_vehicles()
    if not broken:
        await message.answer("Тизимда носоз (таъмирланаётган) автолар топилмади.")
        return
        
    await message.answer(
        "🔴 <b>Носоз ҳолатдаги (таъмирланаётган) avtolar ro'yxati:</b>\n"
        "Тафсилотлар ва фаол заявкаларни кўриш uchun mashinani tanlang:",
        reply_markup=get_vehicles_inline_keyboard(broken),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("veh_list_back_"))
async def process_veh_list_back(callback: CallbackQuery):
    list_type = callback.data.split("_")[3]
    
    if list_type == "soz":
        healthy = await db.get_healthy_vehicles()
        if not healthy:
            await callback.message.edit_text("Тизимда соз автолар топилмади.", reply_markup=None)
            return
        await callback.message.edit_text(
            "🟢 <b>Соз ҳолатдаги автолар рўйхати:</b>\n"
            "Тафсилотлар ва тарихни кўриш uchun mashinani tanlang:",
            reply_markup=get_vehicles_inline_keyboard(healthy, "soz"),
            parse_mode="HTML"
        )
    elif list_type == "nosoz":
        broken = await db.get_broken_vehicles()
        if not broken:
            await callback.message.edit_text("Тизимда носоз (таъмирланаётган) автолар топилмади.", reply_markup=None)
            return
        await callback.message.edit_text(
            "🔴 <b>Носоз ҳолатдаги (таъмирланаётган) автолар рўйхати:</b>\n"
            "Тафсилотлар ва фаол заявкаларни кўриш uchun машинани танланг:",
            reply_markup=get_vehicles_inline_keyboard(broken, "nosoz"),
            parse_mode="HTML"
        )
    else:
        vehicles = await db.get_all_vehicles()
        await callback.message.edit_text(
            "🚗 <b>Тизимдаги барча автолар рўйхати:</b>\n"
            "Ҳолати ва тафсилотларни кўриш учун машинани танланг:",
            reply_markup=get_vehicles_inline_keyboard(vehicles, "all"),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("veh_newreq_"))
async def process_veh_newreq(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ!", show_alert=True)
        return
        
    vehicle_name = callback.data.split("_")[2]
    await state.clear()
    await state.update_data(vehicle_name=vehicle_name, temp_items=[])
    await state.set_state(RequestCreationStates.waiting_for_photo)
    
    skip_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Расм йўқ 🚫")],
        [KeyboardButton(text="Бекор қилиш ❌")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    await callback.message.answer(
        f"🚗 <b>Танланган машина:</b> {vehicle_name}\n\n"
        f"📷 <b>Ески запчаст расмини юборинг (ёки расми бўлмаса, қуйидаги тугмани босинг):</b>",
        reply_markup=skip_kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(RequestCreationStates.waiting_for_photo)
async def process_photo(message: Message, state: FSMContext):
    text = message.text or message.caption
    if text == "Бекор қилиш ❌":
        user = await db.get_user(message.from_user.id)
        await state.clear()
        await message.answer("Заявка бекор қилинди.", reply_markup=get_main_keyboard(user['role']))
        return
        
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif text == "Расм йўқ 🚫":
        photo_id = None
    else:
        await message.answer("Илтимос, расм юборинг yoki 'Расм йўқ 🚫' tugmasini bosing:")
        return

    await state.update_data(old_part_photo=photo_id)
    await state.set_state(RequestCreationStates.waiting_for_requester)
    
    cancel_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Бекор қилиш ❌")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(
        "👤 **Kim so'rayapti?**\n"
        "Buyurtmachining ismi yoki lavozimini yozing:\n"
        "(Masalan: `Ivanov Ivan`, `Brigadir`, `Ҳaydovchi`)",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )

@router.message(RequestCreationStates.waiting_for_requester)
async def process_requester(message: Message, state: FSMContext):
    if message.text == "Бекор қилиш ❌":
        user = await db.get_user(message.from_user.id)
        await state.clear()
        await message.answer("Заявка бекор қилинди.", reply_markup=get_main_keyboard(user['role']))
        return
    
    if not message.text:
        await message.answer("Илтимос, исм ёки лавозим ёзинг:")
        return
    
    await state.update_data(requester_name=message.text.strip())
    await state.set_state(RequestCreationStates.waiting_for_request_type)
    
    type_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛠 Tamirlash", callback_data="reqtype_repair"),
            InlineKeyboardButton(text="🛒 Yangi zapchast", callback_data="reqtype_purchase")
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="reqtype_cancel")]
    ])
    
    await message.answer(
        "📋 **Zayvka turini tanlang:**",
        reply_markup=type_kb,
        parse_mode="Markdown"
    )

@router.callback_query(RequestCreationStates.waiting_for_request_type, F.data.startswith("reqtype_"))
async def process_request_type(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    
    if action == "cancel":
        user = await db.get_user(callback.from_user.id)
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("Заявка бекор қилинди.", reply_markup=get_main_keyboard(user['role']))
        await callback.answer()
        return
    
    req_type = "repair" if action == "repair" else "purchase"
    await state.update_data(forced_request_type=req_type)
    await state.set_state(RequestCreationStates.waiting_for_items_text)
    
    cancel_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Бекор қилиш ❌")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    if req_type == "repair":
        prompt = (
            "🛠 **Tamirlash zayvkasi**\n\n"
            "📝 Tamirlash kerak bo'lgan narsalarni yozing:\n"
            "(Masalan: `generatorni sozlash`, `tormoz yo'gini almashtirish`)"
        )
    else:
        prompt = (
            "🛒 **Yangi zapchast zayvkasi**\n\n"
            "📝 Kerakli zapchastlar ro'yxatini yozing:\n"
            "(Masalan: `2 ta balon`, `4 ta pachivnik`, `1 ta filtr`)"
        )
    
    await callback.answer()
    await callback.message.edit_text(prompt, parse_mode="Markdown")
    await callback.message.answer("⬇️ Yozing:", reply_markup=cancel_kb)

@router.message(RequestCreationStates.waiting_for_items_text)
async def process_items_text(message: Message, state: FSMContext):
    if message.text == "Бекор қилиш ❌":
        user = await db.get_user(message.from_user.id)
        await state.clear()
        await message.answer("Заявка бекор қилинди.", reply_markup=get_main_keyboard(user['role']))
        return
        
    if not message.text:
        await message.answer("Илтимос, маҳсулотларни матн шаклида юборинг:")
        return
        
    text = message.text.strip()
    state_data = await state.get_data()
    forced_type = state_data.get('forced_request_type', None)
    parsed_items = await parse_request_text(text)
    
    if not parsed_items:
        await message.answer(
            "❌ Маҳсулотларни аниқлаб бўлмади. Қўлда киритиш uchun quyidagi tugmani bosing:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ Qo'lda kiritish", callback_data="itemloop_add")]
            ])
        )
        return
        
    if forced_type:
        for item in parsed_items:
            item['type'] = forced_type
    await state.update_data(temp_items=parsed_items)
    await show_loop_decision(message, state)

async def show_loop_decision(message: Message, state: FSMContext):
    await state.set_state(RequestCreationStates.waiting_for_loop_decision)
    state_data = await state.get_data()
    temp_items = state_data.get('temp_items', [])
    
    text = "📦 **Жорий заявка таркиби:**\n"
    for idx, item in enumerate(temp_items, start=1):
        if item['type'] == 'repair':
            text += f"{idx}. 🛠 **[Таъмирлаш]** {item['name']}\n"
        else:
            text += f"{idx}. 🛒 **[Сотиб олиш]** {item['name']} — {item['qty']} та\n"
            
    text += "\n🤔 **Якунлайсизми ёки яна маҳсулот қўшасизми?**"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏁 Якунлаш ва юбориш", callback_data="itemloop_finish"),
            InlineKeyboardButton(text="➕ Яна қўшиш", callback_data="itemloop_add")
        ],
        [InlineKeyboardButton(text="❌ Бекор қилиш", callback_data="itemloop_cancel")]
    ])
    
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(RequestCreationStates.waiting_for_loop_decision, F.data.startswith("itemloop_"))
async def process_loop_decision_callback(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    user = await db.get_user(callback.from_user.id)
    
    if action == 'cancel':
        await state.clear()
        await callback.message.answer("Заявка бекор қилинди.", reply_markup=get_main_keyboard(user['role']))
        await callback.answer()
        return
        
    if action == 'add':
        await state.set_state(RequestCreationStates.waiting_for_manual_item_type)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🛠 Таъмирлаш", callback_data="itemtype_repair"),
                InlineKeyboardButton(text="🛒 Сотиб олиш", callback_data="itemtype_purchase")
            ],
            [InlineKeyboardButton(text="❌ Бекор қилиш", callback_data="itemloop_cancel")]
        ])
        await callback.message.edit_text("⚙️ **Қўшиладиган маҳсулот турини танланг:**", reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
        return
        
    if action == 'finish':
        await finish_request_creation(callback, state, user)
        await callback.answer()
        return

@router.callback_query(RequestCreationStates.waiting_for_manual_item_type, F.data.startswith("itemtype_"))
async def process_manual_item_type(callback: CallbackQuery, state: FSMContext):
    item_type = callback.data.split("_")[1]
    await state.update_data(current_item_type=item_type)
    await state.set_state(RequestCreationStates.waiting_for_manual_item_name)
    
    if item_type == 'repair':
        text = "🛠 **Таъмирланадиган қисм ва муаммони ёзинг:**\n(Масалан: 'Стартер моторни таъмирлаш'):"
    else:
        text = "🛒 **Янги эҳтиёт қисм номини киритинг:**\n(Масалан: 'Мой фильтри'):"
        
    await callback.message.answer(text, reply_markup=ReplyKeyboardRemove())
    await callback.answer()

@router.message(RequestCreationStates.waiting_for_manual_item_name)
async def process_manual_item_name(message: Message, state: FSMContext):
    if message.text == "Бекор қилиш ❌":
        user = await db.get_user(message.from_user.id)
        await state.clear()
        await message.answer("Заявка бекор қилинди.", reply_markup=get_main_keyboard(user['role']))
        return
        
    name = message.text.strip()
    state_data = await state.get_data()
    item_type = state_data.get('current_item_type')
    
    if item_type == 'repair':
        temp_items = state_data.get('temp_items', [])
        temp_items.append({'type': 'repair', 'name': name, 'qty': 1})
        await state.update_data(temp_items=temp_items)
        await show_loop_decision(message, state)
    else:
        await state.update_data(current_item_name=name)
        await message.answer("🔢 **Миқдорини (сонини) butun sonda kiriting:**", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RequestCreationStates.waiting_for_manual_item_qty)

@router.message(RequestCreationStates.waiting_for_manual_item_qty)
async def process_manual_item_qty(message: Message, state: FSMContext):
    if message.text == "Бекор қилиш ❌":
        user = await db.get_user(message.from_user.id)
        await state.clear()
        await message.answer("Заявка бекор қилинди.", reply_markup=get_main_keyboard(user['role']))
        return
        
    try:
        qty = int(message.text.strip())
        if qty <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("Илтимос, нолдан катта бутун сон киритинг:")
        return
        
    state_data = await state.get_data()
    name = state_data.get('current_item_name')
    temp_items = state_data.get('temp_items', [])
    temp_items.append({'type': 'purchase', 'name': name, 'qty': qty})
    await state.update_data(temp_items=temp_items)
    
    await show_loop_decision(message, state)

async def finish_request_creation(callback: CallbackQuery, state: FSMContext, user: dict):
    state_data = await state.get_data()
    temp_items = state_data.get('temp_items', [])
    
    if not temp_items:
        await callback.message.answer("❌ Заявкада ҳеч қандай маҳсулот йўқ! Камида битта маҳсулот киритинг.")
        await state.set_state(RequestCreationStates.waiting_for_items_text)
        return
        
    vehicle_name = state_data['vehicle_name']
    photo_id = state_data['old_part_photo']
    editing_request_id = state_data.get('editing_request_id')
    
    created_request_ids = []
    
    if editing_request_id:
        item = temp_items[0]
        item_type = item['type']
        prefix = "Таъмирлаш: " if item_type == 'repair' else ""
        description = f"Машина: {vehicle_name} | " + (f"Таъмирлаш: {item['name']}" if item_type == 'repair' else f"Сотиб олиш: {item['name']} ({item['qty']} та)")
        
        await db.update_request_details(editing_request_id, description, vehicle_name, photo_id, qty_used=None, qty_left=None, request_type=item_type)
        await db.delete_request_items(editing_request_id)
            
        await db.add_request_item(
            request_id=editing_request_id,
            item_name=f"{prefix}{item['name']}",
            quantity_requested=item['qty'],
            quantity_available=0,
            quantity_missing=item['qty']
        )
        created_request_ids.append(editing_request_id)
        
        admin_prefix = f"🔔 <b>Заявка №{editing_request_id} таҳрирланиб, қайта тасдиқлашга келди!</b>\n\n"
        summary_text = (
            f"📝 <b>Заявка №{editing_request_id} муваффақиятли таҳрирланди ва қайта тасдиқлашга юборилди! 📝</b>\n\n"
            f"🚗 <b>Машина:</b> {vehicle_name}\n"
            f"👤 <b>Юборувчи:</b> {user['full_name']}\n\n"
            f"📋 <b>Заявка таркиби:</b>\n"
            f"   1. " + ("🛠 [Таъмирлаш] " if item_type == 'repair' else "🛒 [Сотиб олиш] ") + f"{item['name']} — {item['qty']} та\n"
        )
        
        managers = await db.get_users_by_role('manager')
        super_admins = await db.get_users_by_role('super_admin')
        observers = await db.get_users_by_role('observer')
        all_admins = list(managers) + list(super_admins) + list(observers)
        for admin in all_admins:
            try:
                from main import bot
                kb = get_request_manage_keyboard(editing_request_id)
                msg_text = admin_prefix + summary_text
                if photo_id:
                    await bot.send_photo(admin['telegram_id'], photo=photo_id, caption=msg_text, reply_markup=kb, parse_mode="HTML")
                else:
                    await bot.send_message(admin['telegram_id'], text=msg_text, reply_markup=kb, parse_mode="HTML")
            except Exception as e:
                print(f"Admin {admin['telegram_id']}ni ogohlantirishda xato: {e}")
    else:
        for item in temp_items:
            item_type = item['type']
            prefix = "Таъмирлаш: " if item_type == 'repair' else ""
            description = f"Машина: {vehicle_name} | " + (f"Таъмирлаш: {item['name']}" if item_type == 'repair' else f"Сотиб олиш: {item['name']} ({item['qty']} та)")
            
            request_id = await db.create_request(
                created_by=callback.from_user.id,
                description=description,
                vehicle_name=vehicle_name,
                old_part_photo=photo_id,
                qty_used=None,
                qty_left=None,
                request_type=item_type
            )
            
            await db.add_request_item(
                request_id=request_id,
                item_name=f"{prefix}{item['name']}",
                quantity_requested=item['qty'],
                quantity_available=0,
                quantity_missing=item['qty']
            )
            created_request_ids.append(request_id)
            
            admin_prefix = f"🔔 <b>Янги заявка тасдиқлаш учун келди! (№{request_id})</b>\n\n"
            summary_text = (
                f"📝 <b>Заявка №{request_id} яратилди ва тасдиқлашга юборилди!</b>\n\n"
                f"🚗 <b>Машина:</b> {vehicle_name}\n"
                f"👤 <b>Юборувчи:</b> {user['full_name']}\n\n"
                f"📋 <b>Заявка таркиби:</b>\n"
                f"   1. " + ("🛠 [Таъмирлаш] " if item_type == 'repair' else "🛒 [Сотиб олиш] ") + f"{item['name']} — {item['qty']} та\n"
            )
            
            managers = await db.get_users_by_role('manager')
            super_admins = await db.get_users_by_role('super_admin')
            observers = await db.get_users_by_role('observer')
            all_admins = list(managers) + list(super_admins) + list(observers)
            for admin in all_admins:
                try:
                    from main import bot
                    kb = get_request_manage_keyboard(request_id)
                    msg_text = admin_prefix + summary_text
                    if photo_id:
                        await bot.send_photo(admin['telegram_id'], photo=photo_id, caption=msg_text, reply_markup=kb, parse_mode="HTML")
                    else:
                        await bot.send_message(admin['telegram_id'], text=msg_text, reply_markup=kb, parse_mode="HTML")
                except Exception as e:
                    print(f"Admin {admin['telegram_id']}ni ogohlantirishda xato: {e}")
                    
    status_desc = "Янги заявкалар: " + ", ".join(f"№{rid}" for rid in created_request_ids)
    await db.update_vehicle_status(vehicle_name, 'nosoz', status_desc)
    await state.clear()
    
    summary_text = (
        f"🎉 <b>Заявкалар муваффақиятли яратилди ва тасдиқлашга юборилди!</b>\n\n"
        f"🚗 <b>Машина:</b> {vehicle_name}\n"
        f"🔢 <b>Яратилган заявка ID'лари:</b> " + ", ".join(f"<b>№{rid}</b>" for rid in created_request_ids) + "\n\n"
        f"📋 <b>Умумий таркиб:</b>\n"
    )
    for idx, item in enumerate(temp_items, start=1):
        if item['type'] == 'repair':
            summary_text += f"   {idx}. 🛠 [Таъмирлаш] {item['name']}\n"
        else:
            summary_text += f"   {idx}. 🛒 [Сотиб олиш] {item['name']} — {item['qty']} та\n"
            
    if photo_id:
        await callback.message.answer_photo(
            photo=photo_id,
            caption=summary_text,
            reply_markup=get_main_keyboard(user['role']),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            summary_text,
            reply_markup=get_main_keyboard(user['role']),
            parse_mode="HTML"
        )

@router.message(F.text.in_(["Mening zayavkalarim 📂", "Менинг заявкаларим 📂"]) | F.text.startswith("Mening zayavkalarim 📂") | F.text.startswith("Менинг заявкаларим 📂"))
async def show_my_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Сизда заявкаларни кўриш ҳуқуқи йўқ.")
        return
        
    my_reqs = await db.get_all_my_requests(message.from_user.id)
    if not my_reqs:
        await message.answer("Сиз ҳали заявка яратмагансиз.")
        return
        
    await message.answer("📂 <b>Сизнинг барча заявкаларингиз:</b>", parse_mode="HTML")
    for r in my_reqs[:15]:
        status_label = STATUS_LABELS.get(r['status'], r['status'])
        text = (
            f"🆔 <b>Заявка №{r['id']}</b>\n"
            f"📋 Тавсиф: {r['description']}\n"
            f"⚙️ Ҳолати: {status_label}\n"
            f"📅 Сана: {db.format_datetime(r['created_at'])}\n"
            f"-------------------\n"
        )
        await message.answer(text, parse_mode="HTML")
        await send_installation_photo(message, r)


@router.message(F.text.in_(["Tugallanmagan zayavkalar ⏳", "Тугалланмаган заявкалар ⏳"]) | F.text.startswith("Tugallanmagan zayavkalar ⏳") | F.text.startswith("Тугалланмаган заявкалар ⏳"))
async def show_unfinished_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Сизда заявкаларни кўриш ҳуқуқи йўқ.")
        return

    active_requests = await db.get_my_requests(message.from_user.id)
    if not active_requests:
        await message.answer("✅ Сизда тугалланмаган заявка мавжуд эмас.")
        return

    text = "⏳ <b>Тугалланмаган заявкаларингиз:</b>\n\n"
    for r in active_requests[:15]:
        status_label = STATUS_LABELS.get(r['status'], r['status'])
        text += (
            f"🆔 <b>Заявка №{r['id']}</b>\n"
            f"🚗 Машина: {r['vehicle_name'] or '—'}\n"
            f"📋 Тавсиф: {r['description']}\n"
            f"⚙️ Ҳолати: <b>{status_label}</b>\n"
            f"📅 Сана: {db.format_datetime(r['created_at'])}\n"
            f"-------------------\n"
        )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text.in_(["Tugallangan zayavkalar ✅", "Тугалланган заявkalar ✅"]) | F.text.startswith("Tugallangan zayavkalar ✅") | F.text.startswith("Тугалланган заявкалар ✅"))
async def show_my_completed_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Сизда ушбу маълумотни кўриш ҳуқуқи йўқ.")
        return

    requests = await db.get_my_completed_requests(message.from_user.id)
    if not requests:
        await message.answer("Ҳозирча сизда тугалланган заявка йўқ.")
        return

    await message.answer("✅ <b>Сизнинг тугалланган заявкаларингиз:</b>", parse_mode="HTML")
    for request in requests:
        await message.answer(
            f"🆔 <b>Заявка №{request['id']}</b>\n"
            f"🚗 Машина: {request['vehicle_name'] or '—'}\n"
            f"📋 Тавсиф: {request['description']}\n"
            f"🕒 Якунланган: {db.format_datetime(request['updated_at'])}",
            parse_mode="HTML",
        )
        await send_installation_photo(message, request)


@router.message(F.text.in_(["Skladdan olish 📦", "Складдан олиш 📦"]) | F.text.startswith("Skladdan olish 📦") | F.text.startswith("Складдан олиш 📦"))
async def show_requests_ready_for_pickup(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Сизда ушбу маълумотни кўриш ҳуқуқи йўқ.")
        return

    requests = await db.get_requests_ready_for_pickup(message.from_user.id)
    if not requests:
        await message.answer("📦 Ҳозирча складдан олишга тайёр маҳсулот йўқ.")
        return

    await message.answer("📦 <b>Складдан олишга тайёр заявкалар:</b>", parse_mode="HTML")
    for request in requests:
        items = await db.get_request_items(request['id'])
        items_text = '\n'.join(
            f"• {item['item_name']} — {item['quantity_requested']} dona" for item in items
        ) or '—'
        await message.answer(
            f"🆔 <b>Заявка №{request['id']}</b>\n"
            f"🚗 Машина: {request['vehicle_name'] or '—'}\n"
            f"📋 Тавсиф: {request['description']}\n"
            f"📦 Маҳсулотлар:\n{items_text}\n\n"
            "Маҳсулотни складдан олганингиздан кейин tasdiqlang.",
            reply_markup=get_mechanic_pickup_keyboard(request['id']),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("mech_pickup_"))
async def confirm_warehouse_pickup(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ.", show_alert=True)
        return

    request_id = int(callback.data.split("_")[2])
    try:
        await db.issue_request_to_creator(request_id, callback.from_user.id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    except Exception as exc:
        print(f"Skladdan olishda xato: {exc}")
        await callback.answer("Skladdan olishni qayd etishda xato yuz berdi.", show_alert=True)
        return

    await callback.message.edit_text(
        f"✅ <b>Заявка №{request_id}</b> бўйича маҳсулотлар складдан олинди.\n"
        "📊 Омбордан расxод қайд этилди. Ўрнатиб бўлгач, расм юбориб якунланг.",
        reply_markup=get_mechanic_install_keyboard(request_id),
        parse_mode="HTML",
    )
    await callback.answer("Mahsulotlar olindi, rasxod qayd etildi.")

@router.callback_query(F.data.startswith("mech_install_"))
async def process_mechanic_install(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    request = await db.get_request(request_id)
    if not request or request['created_by'] != callback.from_user.id:
        await callback.answer("Zayavka topilmadi yoki sizga tegishli emas.", show_alert=True)
        return
    if request['status'] != 'issued_to_mechanic':
        await callback.answer("Avval mahsulotni skladdan qabul qiling.", show_alert=True)
        return
    await state.clear()
    await state.update_data(install_request_id=request_id)
    await state.set_state(RequestInstallationStates.waiting_for_installation_photo)
    
    await callback.message.answer(
        "📸 **Ўрнатилган запчаст (ёки бажарилган иш) исботи:**\n"
        "Илтимос, бажарилган иш ёки ўрнатилган янги эҳтиёт қисм расмини юборинг:",
        reply_markup=ReplyKeyboardRemove()
    )
    await callback.answer()

@router.message(RequestInstallationStates.waiting_for_installation_photo)
async def process_installation_photo(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Илтимос, ўрнатилган запчаст rasmini yuboring (faqat rasm qabul qilinadi):")
        return
        
    photo_id = message.photo[-1].file_id
    await state.update_data(install_photo_id=photo_id)
    
    state_data = await state.get_data()
    request_id = state_data.get('install_request_id')
    
    req = await db.get_request(request_id)
    if not req:
        await message.answer("Заявка топилмади.")
        await state.clear()
        return
        
    is_repair = req.get('request_type') == 'repair'
    if is_repair:
        await db.update_request_installation_details(request_id, photo_id, None)
        await db.update_request_status(request_id, 'completed', message.from_user.id, 'mechanic')
        
        if req['vehicle_name']:
            has_active = await db.check_vehicle_active_requests(req['vehicle_name'])
            if not has_active:
                await db.update_vehicle_status(req['vehicle_name'], 'soz', None)
                
        user = await db.get_user(message.from_user.id)
        await state.clear()
        
        await message.answer(
            "🎉 Раҳмат! Таъмирлаш бўйича заявка муваффақиятли якунланди va yopildi.\n"
            "Isbot rasmi rahbariyatga yuborildi.",
            reply_markup=get_main_keyboard(user['role'])
        )
        await notify_admins_completed(request_id, req, photo_id, user)
        return
        
    items = await db.get_request_items(request_id)
    if not items:
        await message.answer("Заявкада маҳсулотлар топилмади.")
        await state.clear()
        return
        
    await state.update_data(
        items_list=[{'id': item['id'], 'name': item['item_name'], 'req': item['quantity_requested']} for item in items],
        current_idx=0,
        items_used_map={}
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ҳаммаси ўрнатилди", callback_data="instconfirm_all"),
            InlineKeyboardButton(text="⚠️ Қисман ўрнатилди", callback_data="instconfirm_part")
        ]
    ])
    
    await message.answer(
        "⚙️ **Эҳтиёт қисмларни ўрнатиш ҳолати:**\n"
        "Барча сўралган va olingan zapchastlar mashinaga o'rnatildimi?",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("instconfirm_"))
async def process_install_confirm_callback(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    state_data = await state.get_data()
    request_id = state_data.get('install_request_id')
    photo_id = state_data.get('install_photo_id')
    user = await db.get_user(callback.from_user.id)
    
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Заявка топилмади.")
        await state.clear()
        return
        
    if action == 'all':
        await db.update_request_installation_details(request_id, photo_id, None)
        await db.update_request_status(request_id, 'completed', callback.from_user.id, 'mechanic')
        
        if req['vehicle_name']:
            has_active = await db.check_vehicle_active_requests(req['vehicle_name'])
            if not has_active:
                await db.update_vehicle_status(req['vehicle_name'], 'soz', None)
                
        await state.clear()
        await callback.message.edit_text(
            "🎉 Раҳмат! Барча запчастлар муваффақиятли ўрнатилди va zayavka yopildi.\n"
            "Hisobot va isbot rasmi rahbariyatga yuborildi.",
            reply_markup=None
        )
        await callback.message.answer("Асосий меню:", reply_markup=get_main_keyboard(user['role']))
        await notify_admins_completed(request_id, req, photo_id, user)
        await callback.answer()
        return
        
    if action == 'part':
        await callback.answer()
        await ask_next_item_install_qty(callback.message, state)

async def ask_next_item_install_qty(message: Message, state: FSMContext):
    state_data = await state.get_data()
    items_list = state_data.get('items_list', [])
    current_idx = state_data.get('current_idx', 0)
    
    if current_idx < len(items_list):
        item = items_list[current_idx]
        await state.set_state(RequestInstallationStates.waiting_for_qty_used)
        await message.answer(
            f"🔢 **{item['name']}**\n"
            f"Олинган {item['req']} tadan nechtasi mashinaga o'rnatildi/ishlatildi? (0 va {item['req']} oralig'ida son yozing):",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        request_id = state_data.get('install_request_id')
        photo_id = state_data.get('install_photo_id')
        items_used_map = state_data.get('items_used_map', {})
        user = await db.get_user(message.from_user.id)
        
        req = await db.get_request(request_id)
        
        await db.update_request_installation_details(request_id, photo_id, items_used_map)
        await db.update_request_status(request_id, 'completed', message.from_user.id, 'mechanic')
        
        if req and req['vehicle_name']:
            has_active = await db.check_vehicle_active_requests(req['vehicle_name'])
            if not has_active:
                await db.update_vehicle_status(req['vehicle_name'], 'soz', None)
                
        await state.clear()
        
        summary_lines = []
        for item in items_list:
            used = items_used_map.get(str(item['id']), item['req'])
            left = item['req'] - used
            summary_lines.append(f"🔹 **{item['name']}** — Ишлатилди: {used} та | Қолди: {left} та")
            
        await message.answer(
            f"🎉 Раҳмат! Заявка муваффақиятли якунланди va yopildi.\n"
            f"📊 **Ҳисобот:**\n" + "\n".join(summary_lines) + "\n\nIsbot rasmi va hisobot rahbariyatga yuborildi.",
            reply_markup=get_main_keyboard(user['role'])
        )
        await notify_admins_completed(request_id, req, photo_id, user, items_list, items_used_map)

async def notify_admins_completed(request_id: int, req: dict, photo_id: str, user: dict, items_list: list = None, items_used_map: dict = None):
    managers = await db.get_users_by_role('manager')
    super_admins = await db.get_users_by_role('super_admin')
    all_admins = list(managers) + list(super_admins)
    
    created_date = req['created_at'][:16].replace('T', ' ')
    is_repair = req.get('request_type') == 'repair'
    
    if is_repair:
        msg_text = (
            f"✅ <b>Таъмирлаш заявкаси №{request_id} ёпилди</b>\n\n"
            f"🚗 <b>Машина:</b> {req['vehicle_name']}\n"
            f"🛠 <b>Таъмирлаш:</b> {req['description']}\n"
            f"👤 <b>Механик:</b> {user['full_name']}\n"
            f"📅 <b>Сана:</b> {created_date}\n\n"
            f"Таъмирлаш-созлаш исбот расми илова қилинди."
        )
    else:
        item_details_text = ""
        if items_list and items_used_map:
            for item in items_list:
                used = items_used_map.get(str(item['id']), item['req'])
                left = item['req'] - used
                item_details_text += f"   • {item['name']}: {item['req']} тадан -> Ишлатилди: {used} та, Қолди: {left} та\n"
        else:
            item_details_text = f"   • Ҳамма олинgan qismlar to'liq o'rnatildi.\n"
            
        msg_text = (
            f"✅ <b>Заявка №{request_id} ёпилди (Исбот расми ва ҳисобот юборилди)</b>\n\n"
            f"🚗 <b>Машина:</b> {req['vehicle_name']}\n"
            f"👤 <b>Механик:</b> {user['full_name']}\n"
            f"📊 <b>Деталлар бўйича ҳисобот:</b>\n{item_details_text}"
            f"📅 <b>Сана:</b> {created_date}\n\n"
            f"Ўрнатилган янги эҳтиёт қисм исбот расми илова қилинди."
        )
        
    for adm in all_admins:
        try:
            from main import bot
            await bot.send_photo(
                adm['telegram_id'],
                photo=photo_id,
                caption=msg_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Admin {adm['telegram_id']} ga o'rnatish rasmini yuborishda xato: {e}")

@router.message(RequestInstallationStates.waiting_for_qty_used)
async def process_installation_qty_used(message: Message, state: FSMContext):
    state_data = await state.get_data()
    items_list = state_data.get('items_list', [])
    current_idx = state_data.get('current_idx', 0)
    items_used_map = state_data.get('items_used_map', {})
    
    if current_idx >= len(items_list):
        await state.clear()
        return
        
    item = items_list[current_idx]
    
    try:
        qty_used = int(message.text.strip())
        if qty_used < 0 or qty_used > item['req']:
            raise ValueError()
    except ValueError:
        await message.answer(f"Илтимос, 0 va {item['req']} oralig'idagi butun son kiriting:")
        return
        
    items_used_map[str(item['id'])] = qty_used
    await state.update_data(items_used_map=items_used_map, current_idx=current_idx + 1)
    
    await ask_next_item_install_qty(message, state)

@router.callback_query(F.data.startswith("mech_resubmit_"))
async def process_mechanic_resubmit(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    await state.clear()
    await state.update_data(editing_request_id=request_id)
    await state.set_state(RequestCreationStates.waiting_for_vehicle)
    
    keyboard = []
    row = []
    for veh in db.PREDEFINED_VEHICLES:
        row.append(KeyboardButton(text=veh))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    
    await callback.message.answer(
        f"📝 **Заявка №{request_id} ни таҳрирлаш (1/4):**\n"
        f"Илтимос, рўйхатдан транспорт воситасини танланг:",
        reply_markup=markup
    )
    await callback.answer()
