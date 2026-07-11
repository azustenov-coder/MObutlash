from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import aiosqlite
import database as db
from handlers.common import get_main_keyboard, get_request_manage_keyboard
from handlers.controller import STATUS_LABELS

router = Router()

class RequestCreationStates(StatesGroup):
    waiting_for_vehicle = State()
    waiting_for_request_type = State()
    waiting_for_photo = State()
    waiting_for_repair_desc = State()
    waiting_for_part_name = State()
    waiting_for_qty = State()
    waiting_for_qty_used = State()
    waiting_for_qty_left = State()
    waiting_for_breakdown_reason = State()

class RequestInstallationStates(StatesGroup):
    waiting_for_installation_photo = State()
    waiting_for_qty_used = State()
    waiting_for_qty_left = State()

def get_request_type_keyboard(vehicle_name: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛠 Таъмирlash", callback_data=f"veh_reqtype_{vehicle_name}_repair"),
            InlineKeyboardButton(text="🛒 Сотиб олиш", callback_data=f"veh_reqtype_{vehicle_name}_purchase")
        ],
        [
            InlineKeyboardButton(text="🛠 Таъмирлаш ва 🛒 Сотиб олиш", callback_data=f"veh_reqtype_{vehicle_name}_both")
        ]
    ])

# Helper to generate vehicles inline keyboard grid
def get_vehicles_inline_keyboard(vehicles_list):
    keyboard = []
    row = []
    for veh in vehicles_list:
        keyboard_button = InlineKeyboardButton(text=veh, callback_data=f"veh_info_{veh}")
        row.append(keyboard_button)
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(F.text.in_(["Soz avtolar 🟢", "Соз автолар 🟢"]))
async def show_healthy_vehicles(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    healthy = await db.get_healthy_vehicles()
    if not healthy:
        await message.answer("Тизимда соз автолар топилмаdi.")
        return
        
    await message.answer(
        "🟢 **Соз ҳолатдаги автолар рўйхати:**\n"
        "Тафсилотлар ва тарихни кўриш uchun mashinani tanlang:",
        reply_markup=get_vehicles_inline_keyboard(healthy),
        parse_mode="Markdown"
    )

@router.message(F.text.in_(["Nosoz avtolar 🔴", "Носоз автолар 🔴"]))
async def show_broken_vehicles(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    broken = await db.get_broken_vehicles()
    if not broken:
        await message.answer("Тизимда носоз (таъмирланаётган) автолар топилмади.")
        return
        
    await message.answer(
        "🔴 **Носоз ҳолатдаги (таъмирланаётган) автолар рўйхати:**\n"
        "Тафсилотлар ва фаол заявкаларни кўриш учун машинани танланг:",
        reply_markup=get_vehicles_inline_keyboard(broken),
        parse_mode="Markdown"
    )

@router.message(F.text.in_(["Avtolar 🚗", "Автолар 🚗"]))
async def show_all_vehicles(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    vehicles = await db.get_all_vehicles()
    if not vehicles:
        await message.answer("Тизимда бирорта ҳам автоулов топилмади.")
        return
        
    await message.answer(
        "🚗 **Тизимдаги барча автолар рўйхати:**\n"
        "Тафсилотларни кўриш ёки заявка очиш учун машинани танланг:",
        reply_markup=get_vehicles_inline_keyboard(vehicles),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("veh_info_"))
async def process_vehicle_info(callback: CallbackQuery):
    vehicle_name = callback.data.split("_")[2]
    
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("""
            SELECT r.*, u.full_name as creator_name 
            FROM requests r 
            JOIN users u ON r.created_by = u.telegram_id 
            WHERE r.vehicle_name = ? AND r.status NOT IN ('completed', 'rejected')
            ORDER BY r.id DESC
        """, (vehicle_name,)) as cursor:
            active_requests = await cursor.fetchall()
            
        async with conn.execute("""
            SELECT r.*, u.full_name as creator_name 
            FROM requests r 
            JOIN users u ON r.created_by = u.telegram_id 
            WHERE r.vehicle_name = ? AND r.status IN ('completed', 'rejected')
            ORDER BY r.id DESC LIMIT 5
        """, (vehicle_name,)) as cursor:
            history_requests = await cursor.fetchall()
            
    # Query vehicle status and reason from vehicles table
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT status, reason FROM vehicles WHERE name = ?", (vehicle_name,)) as cursor:
            row = await cursor.fetchone()
            veh_status = row['status'] if row else 'soz'
            veh_reason = row['reason'] if row else None
            
    status_emoji = "🔴 Носоз" if veh_status == 'nosoz' else "🟢 Соз"
    
    text = (
        f"🚗 <b>Автомобил:</b> {vehicle_name}\n"
        f"⚙️ <b>Ҳолати:</b> {status_emoji}\n"
    )
    if veh_status == 'nosoz' and veh_reason:
        text += f"💬 <b>Сабаби:</b> {veh_reason}\n"
    text += "\n"
    
    if active_requests:
        text += "⚠️ <b>Фаол бузилишлар ва заявкалар:</b>\n"
        for r in active_requests:
            created_date = r['created_at'][:16].replace('T', ' ')
            status_label = STATUS_LABELS.get(r['status'], r['status'])
            text += (
                f"   • 🆔 <b>Заявка №{r['id']}</b> ({status_label})\n"
                f"     Тавсиф: {r['description']}\n"
                f"     Сана: {created_date}\n\n"
            )
    else:
        text += "✅ <i>Ушбу машинада фаол бузилишлар ёки заявкалар мавжуд эмас.</i>\n\n"
        
    if history_requests:
        text += "📋 <b>Охирги таъмирлаш тарихи (максимум 5 та):</b>\n"
        for r in history_requests:
            closed_date = r['updated_at'][:16].replace('T', ' ') if r['updated_at'] else "—"
            status_label = STATUS_LABELS.get(r['status'], r['status'])
            text += f"   • Заявка №{r['id']} — {r['description']} ({status_label}, {closed_date})\n"
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Соз қилиш", callback_data=f"veh_setstatus_{vehicle_name}_soz"),
            InlineKeyboardButton(text="🔴 Носоз қилиш", callback_data=f"veh_setstatus_{vehicle_name}_nosoz")
        ],
        [InlineKeyboardButton(text="✍️ Ушбу машина учун заявка очиш", callback_data=f"veh_newreq_{vehicle_name}")],
        [InlineKeyboardButton(text="🔙 Орқага", callback_data="veh_list_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("veh_setstatus_"))
async def process_veh_setstatus(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
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
            await callback.message.edit_text("Тизимда соз автолар топилмади.", reply_markup=None)
            return
            
        await callback.message.edit_text(
            "🟢 <b>Соз ҳолатдаги avtolar ro'yxati:</b>\n"
            "Тафсилотлар ва тарихни кўриш uchun mashinani tanlang:",
            reply_markup=get_vehicles_inline_keyboard(healthy),
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
            f"🔴 <b>{vehicle_name}</b> ни Носоз деб белгилаш сабабини (носозликни) ёзинг:\n"
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
        "Тафсилотлар ва фаол заявкаларни кўриш учун машинани танланг:",
        reply_markup=get_vehicles_inline_keyboard(broken),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "veh_list_back")
async def process_veh_list_back(callback: CallbackQuery):
    vehicles = await db.get_all_vehicles()
    await callback.message.edit_text(
        "🚗 <b>Тизимдаги барча автолар рўйхати:</b>\n"
        "Тафсилотlarni ko'rish yoki zayavka ochish uchun mashinani tanlang:",
        reply_markup=get_vehicles_inline_keyboard(vehicles),
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
    await state.set_state(RequestCreationStates.waiting_for_request_type)
    
    await callback.message.answer(
        f"🚗 <b>Танланган машина:</b> {vehicle_name}\n\n"
        f"📋 <b>Сўров турини танланг (2/7):</b>",
        reply_markup=get_request_type_keyboard(vehicle_name),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("veh_reqtype_"))
async def process_request_type_callback(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    vehicle_name = parts[2]
    req_type = parts[3]
    
    await state.update_data(vehicle_name=vehicle_name, request_type=req_type)
    await state.set_state(RequestCreationStates.waiting_for_photo)
    
    skip_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Расм йўқ 🚫")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    if req_type == 'repair':
        type_label = "🛠 Таъмирлаш"
    elif req_type == 'purchase':
        type_label = "🛒 Сотиб олиш"
    else:
        type_label = "🛠 Таъмирлаш ва 🛒 Сотиб олиш"
        
    await callback.message.answer(
        f"🚗 <b>Танланган машина:</b> {vehicle_name}\n"
        f"📋 <b>Сўров тури:</b> {type_label}\n\n"
        f"📷 <b>Ески запчаст rasmi (3/7):</b>\n"
        f"Ески запчаст расмини юборинг (ёки rasmi bo'lmasa, quyidagi tugmani bosing):",
        reply_markup=skip_kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(RequestCreationStates.waiting_for_photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.text == "Расм йўқ 🚫":
        photo_id = None
    else:
        await message.answer("Илтимос, расм юборинг ёки 'Расм йўқ 🚫' тугмасини босинг:")
        return

    await state.update_data(old_part_photo=photo_id)
    
    state_data = await state.get_data()
    req_type = state_data.get('request_type', 'repair')
    
    if req_type == 'repair':
        await message.answer(
            "🛠 **Нимани таъмирлаш кераклигини ёзинг:**\n"
            "Илтимос, таъмирланадиган қисм ва муаммони ёзинг (Масалан: 'Стартерни таъмирлаш' ёки 'Генераторни қайта ўраш'):",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(RequestCreationStates.waiting_for_part_name)
    elif req_type == 'both':
        await message.answer(
            "🛠 **Нимани таъмирлаш кераклигини ёзинг:**\n"
            "Илтимос, таъмирланадиган қисм ва муаммони ёзинг (Масалан: 'Стартерни таъмирлаш' ёки 'Генераторни қайта ўраш'):",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(RequestCreationStates.waiting_for_repair_desc)
    else:
        await message.answer(
            "⚙️ **Янги запчаст номи (4/7):**\n"
            "Сўралаётган янги эҳтиёт қисм номини киритинг (Масалан: 'Мой фильтри' ёки 'Гидравлик шланка'):",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(RequestCreationStates.waiting_for_part_name)

@router.message(RequestCreationStates.waiting_for_repair_desc)
async def process_repair_desc(message: Message, state: FSMContext):
    repair_desc = message.text.strip()
    await state.update_data(repair_desc=repair_desc)
    
    await message.answer(
        "⚙️ **Сотиб олинадиган янги запчаст номини ёзинг (4/7):**\n"
        "Сўралаётган янги эҳтиёт қисм номини киритинг (Масалан: 'Бендикс' ёки 'Стартер мотор'):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RequestCreationStates.waiting_for_part_name)

@router.message(RequestCreationStates.waiting_for_part_name)
async def process_part_name(message: Message, state: FSMContext):
    part_name = message.text.strip()
    await state.update_data(part_name=part_name)
    
    state_data = await state.get_data()
    request_type = state_data.get('request_type', 'repair')
    
    if request_type == 'repair':
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        
        vehicle_name = state_data['vehicle_name']
        photo_id = state_data['old_part_photo']
        editing_request_id = state_data.get('editing_request_id')
        
        description = f"Машина: {vehicle_name} | Таъмирлаш: {part_name}"
        
        if editing_request_id:
            request_id = editing_request_id
            await db.update_request_details(request_id, description, vehicle_name, photo_id, qty_used=None, qty_left=None, request_type='repair')
            await db.update_request_item(request_id, part_name, 1)
            action_verb = "муваффақиятли таҳрирланди ва қайта тасдиқлашга юборилди! 📝"
            admin_prefix = f"🔔 **Таъмирлаш бўйича заявка №{request_id} таҳрирланиб, қайта тасдиқлашга келди!**\n\n"
        else:
            request_id = await db.create_request(
                created_by=user_id,
                description=description,
                vehicle_name=vehicle_name,
                old_part_photo=photo_id,
                qty_used=None,
                qty_left=None,
                request_type='repair'
            )
            await db.add_request_item(
                request_id=request_id,
                item_name=part_name,
                quantity_requested=1,
                quantity_available=0,
                quantity_missing=1
            )
            action_verb = "муваффақиятли яратилди ва тасдиқлашга юборилди!"
            admin_prefix = f"🔔 **Таъмирлаш бўйича янги заявка келди! (№{request_id})**\n\n"
            
        await db.update_vehicle_status(vehicle_name, 'nosoz', f"Таъмирлаш: {part_name}")
        await state.clear()
        
        summary_text = (
            f"📝 **Заявка №{request_id} {action_verb}**\n\n"
            f"📋 **Заявка таркиби:**\n"
            f"🚗 **Машина:** {vehicle_name}\n"
            f"⚙️ **Сўров тури:** 🛠 Таъмирлаш\n"
            f"🔧 **Таъмирланадиган қисм:** {part_name}\n"
            f"👤 **Юборувчи:** {user['full_name']}"
        )
        
        if photo_id:
            await message.answer_photo(
                photo=photo_id,
                caption=summary_text,
                reply_markup=get_main_keyboard(user['role']),
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                summary_text,
                reply_markup=get_main_keyboard(user['role']),
                parse_mode="Markdown"
            )
            
        async def notify_admins(admin_list):
            from main import bot
            for admin in admin_list:
                try:
                    msg_text = admin_prefix + summary_text
                    kb = get_request_manage_keyboard(request_id)
                    if photo_id:
                        await bot.send_photo(admin['telegram_id'], photo=photo_id, caption=msg_text, reply_markup=kb, parse_mode="Markdown")
                    else:
                        await bot.send_message(admin['telegram_id'], text=msg_text, reply_markup=kb, parse_mode="Markdown")
                except Exception as e:
                    print(f"Admin {admin['telegram_id']}ni ogohlantirishda xato: {e}")
                    
        managers = await db.get_users_by_role('manager')
        super_admins = await db.get_users_by_role('super_admin')
        
        await notify_admins(managers)
        await notify_admins(super_admins)
        return
        
    qty_prompt = "Керакли miqdorini kiriting (фақат бутун сон, масалан: 2, 5, 10):"
    if request_type == 'both':
        qty_prompt = f"Сотиб олинадиган '{part_name}' дан нечта керак? (Фақат бутун сон, масалан: 1, 2, 5):"
        
    await message.answer(
        f"🔢 **Нечта керак (5/7):**\n{qty_prompt}",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RequestCreationStates.waiting_for_qty)

@router.message(RequestCreationStates.waiting_for_qty)
async def process_qty(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
        if qty <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("Илтимос, нолдан катта бутун сон киритинг:")
        return
        
    await state.update_data(qty=qty)
    await message.answer(
        f"🛠 **Нечтаси ишлатилади (6/7):**\n"
        f"Илтимос, ишлатиладиган миқдорни киритинг (0 ва {qty} оралиғида):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RequestCreationStates.waiting_for_qty_used)

@router.message(RequestCreationStates.waiting_for_qty_used)
async def process_qty_used(message: Message, state: FSMContext):
    state_data = await state.get_data()
    qty = state_data.get('qty', 0)
    try:
        qty_used = int(message.text.strip())
        if qty_used < 0 or qty_used > qty:
            raise ValueError()
    except ValueError:
        await message.answer(f"Илтимос, 0 ва {qty} оралиғидаги бутун сон киритинг:")
        return
        
    await state.update_data(qty_used=qty_used)
    qty_left_expected = qty - qty_used
    await message.answer(
        f"📦 **Нечтаси омборда қолади (7/7):**\n"
        f"Нечтаси омборда қолишини киритинг (йиғинди тўғри бўлиши учун {qty_left_expected} бўлиши керак, сон киритинг):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RequestCreationStates.waiting_for_qty_left)

@router.message(RequestCreationStates.waiting_for_qty_left)
async def process_qty_left(message: Message, state: FSMContext):
    state_data = await state.get_data()
    qty = state_data.get('qty', 0)
    qty_used = state_data.get('qty_used', 0)
    request_type = state_data.get('request_type', 'repair')
    
    try:
        qty_left = int(message.text.strip())
        if qty_left < 0:
            raise ValueError()
    except ValueError:
        await message.answer("Илтимос, нол ёки ундан катта бутун сон киритинг:")
        return
        
    if qty_used + qty_left != qty:
        qty_left_expected = qty - qty_used
        await message.answer(
            f"❌ Хатолик! Ишлатиладиган ({qty_used}) ва омборда қоладиган ({qty_left}) миқдорлар йиғиндиси "
            f"жами олинадиган ({qty}) га тенг бўлиши керак.\n"
            f"Илтимос, омборда қоладиган миқдорни қайтадан киритинг (кутилаётган: {qty_left_expected}):"
        )
        return

    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    vehicle_name = state_data['vehicle_name']
    photo_id = state_data['old_part_photo']
    part_name = state_data['part_name']
    editing_request_id = state_data.get('editing_request_id')
    
    if request_type == 'both':
        repair_desc = state_data.get('repair_desc', '')
        description = f"Машина: {vehicle_name} | Таъмирлаш: {repair_desc} | Сотиб олиш: {part_name} ({qty} та)"
    else:
        description = f"Машина: {vehicle_name} | Қисм: {part_name} ({qty} та)"
    
    if editing_request_id:
        request_id = editing_request_id
        await db.update_request_details(request_id, description, vehicle_name, photo_id, qty_used, qty_left, request_type)
        await db.update_request_item(request_id, part_name, qty)
        action_verb = "муваффақиятли таҳрирланди ва қайта тасдиқлашга юборилди! 📝"
        admin_prefix = f"🔔 **Заявка №{request_id} таҳрирланиб, қайта тасдиқлашга келди!**\n\n"
    else:
        request_id = await db.create_request(
            created_by=user_id,
            description=description,
            vehicle_name=vehicle_name,
            old_part_photo=photo_id,
            qty_used=qty_used,
            qty_left=qty_left,
            request_type=request_type
        )
        if request_type == 'both':
            repair_desc = state_data.get('repair_desc', '')
            await db.add_request_item(
                request_id=request_id,
                item_name=f"Таъмирлаш: {repair_desc}",
                quantity_requested=1,
                quantity_available=0,
                quantity_missing=1
            )
            await db.add_request_item(
                request_id=request_id,
                item_name=part_name,
                quantity_requested=qty,
                quantity_available=0,
                quantity_missing=qty
            )
        else:
            await db.add_request_item(
                request_id=request_id,
                item_name=part_name,
                quantity_requested=qty,
                quantity_available=0,
                quantity_missing=qty
            )
        action_verb = "муваффақиятли яратилди ва тасдиқлашга юборилди!"
        admin_prefix = f"🔔 **Янги заявка тасдиқлаш учун келди! (№{request_id})**\n\n"
        
    await db.update_vehicle_status(vehicle_name, 'nosoz', "Заявка очилди")
    
    await state.clear()
    
    if request_type == 'both':
        type_label = "🛠 Таъмирлаш ва 🛒 Сотиб олиш"
        repair_desc = state_data.get('repair_desc', '')
        summary_text = (
            f"📝 **Заявка №{request_id} {action_verb}**\n\n"
            f"📋 **Заявка таркиби:**\n"
            f"🚗 **Машина:** {vehicle_name}\n"
            f"⚙️ **Сўров тури:** {type_label}\n"
            f"🛠 **Таъмирланадиган қисм:** {repair_desc}\n"
            f"🔧 **Сотиб олинадиган запчаст:** {part_name}\n"
            f"🔢 **Жами олинган:** {qty} та\n"
            f"🛠 **Ишлатилади:** {qty_used} та\n"
            f"📦 **Омборда қолди:** {qty_left} та\n"
            f"👤 **Юборувчи:** {user['full_name']}"
        )
    else:
        type_label = "🛒 Сотиб олиш"
        summary_text = (
            f"📝 **Заявка №{request_id} {action_verb}**\n\n"
            f"📋 **Заявка таркиби:**\n"
            f"🚗 **Машина:** {vehicle_name}\n"
            f"⚙️ **Сўров тури:** {type_label}\n"
            f"🔧 **Запчаст:** {part_name}\n"
            f"🔢 **Жами олинган:** {qty} та\n"
            f"🛠 **Ишлатилади:** {qty_used} та\n"
            f"📦 **Омборда қолди:** {qty_left} та\n"
            f"👤 **Юборувчи:** {user['full_name']}"
        )
        
    if photo_id:
        await message.answer_photo(
            photo=photo_id,
            caption=summary_text,
            reply_markup=get_main_keyboard(user['role']),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            summary_text,
            reply_markup=get_main_keyboard(user['role']),
            parse_mode="Markdown"
        )
        
    async def notify_admins(admin_list):
        from main import bot
        for admin in admin_list:
            try:
                msg_text = admin_prefix + summary_text
                kb = get_request_manage_keyboard(request_id)
                if photo_id:
                    await bot.send_photo(admin['telegram_id'], photo=photo_id, caption=msg_text, reply_markup=kb, parse_mode="Markdown")
                else:
                    await bot.send_message(admin['telegram_id'], text=msg_text, reply_markup=kb, parse_mode="Markdown")
            except Exception as e:
                print(f"Admin {admin['telegram_id']}ni ogohlantirishda xato: {e}")
                
    managers = await db.get_users_by_role('manager')
    super_admins = await db.get_users_by_role('super_admin')
    
    await notify_admins(managers)
    await notify_admins(super_admins)

@router.message(F.text.in_(["Mening zayavkalarim 📂", "Менинг заявкаларим 📂"]))
async def show_my_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Сизда заявкаларни кўриш ҳуқуқи йўқ.")
        return
        
    my_reqs = await db.get_my_requests(message.from_user.id)
    if not my_reqs:
        await message.answer("Сизда фаол (якунланмаган) заявкалар мавжуд эмас.")
        return
        
    text = "📂 <b>Сизнинг заявкаларингиз рўйхати:</b>\n\n"
    for r in my_reqs[:15]:
        status_label = STATUS_LABELS.get(r['status'], r['status'])
        text += (
            f"🆔 <b>Заявка №{r['id']}</b>\n"
            f"📋 Тавсиф: {r['description']}\n"
            f"⚙️ Ҳолати: {status_label}\n"
            f"📅 Сана: {r['created_at'][:16].replace('T', ' ')}\n"
            f"-------------------\n"
        )
    await message.answer(text, parse_mode="HTML")

@router.callback_query(F.data.startswith("mech_install_"))
async def process_mechanic_install(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    await state.update_data(install_request_id=request_id)
    await state.set_state(RequestInstallationStates.waiting_for_installation_photo)
    
    await callback.message.answer(
        "📸 **Ўрнатилган запчаст исботи:**\n"
        "Илтимос, ўрнатилган янги эҳтиёт қисм расмини юборинг:",
        reply_markup=ReplyKeyboardRemove()
    )
    await callback.answer()

@router.message(RequestInstallationStates.waiting_for_installation_photo)
async def process_installation_photo(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Илтимос, ўрнатилган запчаст расмини юборинг (фақат расм қабул қилинади):")
        return
        
    photo_id = message.photo[-1].file_id
    await state.update_data(install_photo_id=photo_id)
    
    state_data = await state.get_data()
    request_id = state_data.get('install_request_id')
    
    items = await db.get_request_items(request_id)
    qty_requested = items[0]['quantity_requested'] if items else 0
    await state.update_data(qty_requested=qty_requested)
    
    req = await db.get_request(request_id)
    if req and (req['request_type'] == 'repair' or (req['quantity_used'] is not None and req['quantity_left'] is not None)):
        qty_used = req['quantity_used'] if req['quantity_used'] is not None else 0
        qty_left = req['quantity_left'] if req['quantity_left'] is not None else 0
        
        await db.update_request_installation_details(request_id, photo_id, qty_used, qty_left)
        await db.update_request_status(request_id, 'completed', message.from_user.id, 'mechanic')
        
        if req['vehicle_name']:
            has_active = await db.check_vehicle_active_requests(req['vehicle_name'])
            if not has_active:
                await db.update_vehicle_status(req['vehicle_name'], 'soz', None)
                
        user = await db.get_user(message.from_user.id)
        await state.clear()
        
        is_repair = req.get('request_type') == 'repair'
        
        if is_repair:
            await message.answer(
                f"🎉 Раҳмат! Таъмирлаш бўйича заявка муваффақиятли якунланди ва ёпилди.\n"
                f"Исбот расми раҳбариятга юборилди.",
                reply_markup=get_main_keyboard(user['role'])
            )
        else:
            await message.answer(
                f"🎉 Раҳмат! Заявка муваффақиятли якунланди ва ёпилди.\n"
                f"📊 **Ҳисобот (Заявка яратилаётганда киритилган):**\n"
                f"🔹 Ишлатилди: {qty_used} та\n"
                f"🔹 Омборда қолди: {qty_left} та\n"
                f"Исбот расми ва маълумотлар раҳбариятга юборилди.",
                reply_markup=get_main_keyboard(user['role'])
            )
        
        managers = await db.get_users_by_role('manager')
        super_admins = await db.get_users_by_role('super_admin')
        all_admins = list(managers) + list(super_admins)
        
        created_date = req['created_at'][:16].replace('T', ' ')
        if is_repair:
            msg_text = (
                f"✅ <b>Таъмирлаш заявкаси №{request_id} ёпилди</b>\n\n"
                f"🚗 <b>Машина:</b> {req['vehicle_name']}\n"
                f"🛠 <b>Таъмирлаш:</b> {req['description']}\n"
                f"👤 <b>Механик:</b> {user['full_name']}\n"
                f"📅 <b>Сана:</b> {created_date}\n\n"
                f"Таъмирлаш исбот расми илова қилинди."
            )
        else:
            msg_text = (
                f"✅ <b>Заявка №{request_id} ёпилди (Исбот расми ва ҳисобот юборилди)</b>\n\n"
                f"🚗 <b>Машина:</b> {req['vehicle_name']}\n"
                f"⚙️ <b>Запчаст:</b> {req['description']}\n"
                f"👤 <b>Механик:</b> {user['full_name']}\n"
                f"🔢 <b>Жами олинган:</b> {qty_requested} та\n"
                f"🛠 <b>Ишлатилди:</b> {qty_used} та\n"
                f"📦 <b>Омборда қолди:</b> {qty_left} та\n"
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
        return
        
    await message.answer(
        f"🔢 **Ишлатилган миқдори:**\n"
        f"Жами олинган {qty_requested} та запчастдан нечтаси машинага ўрнатилди/ишлатилди? (Бутун сон киритинг, масалан: {qty_requested}):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RequestInstallationStates.waiting_for_qty_used)

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
