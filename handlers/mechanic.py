from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import aiosqlite
import database as db
import os
import json
import re
import aiohttp
from handlers.common import get_main_keyboard, get_request_manage_keyboard
from handlers.controller import STATUS_LABELS

router = Router()

class RequestCreationStates(StatesGroup):
    waiting_for_vehicle = State()
    waiting_for_photo = State()
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

# AI/Regex parser functions
async def parse_request_text(text: str) -> list:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            parsed = await parse_with_gemini(text, gemini_key)
            if parsed:
                return parsed
        except Exception as e:
            print(f"Gemini API parse failed: {e}")
            
    # Fallback to regex parser
    return parse_with_regex(text)

async def parse_with_gemini(text: str, api_key: str) -> list:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{
                "text": (
                    "Parse this request for vehicle parts/repairs (Uzbek/Russian/mix) into a structured JSON array.\n"
                    "Each item must be an object with:\n"
                    "- 'type': 'repair' or 'purchase'\n"
                    "- 'name': string (the part name in Latin Uzbek or Russian. E.g. 'pachivnik' or 'balon')\n"
                    "- 'qty': integer (how many requested, default 1)\n"
                    "\n"
                    f"Text: \"{text}\"\n"
                    "Return ONLY JSON array."
                )
            }]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    headers = {"Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
            if resp.status == 200:
                result = await resp.json()
                content = result['candidates'][0]['content']['parts'][0]['text']
                data = json.loads(content.strip())
                if isinstance(data, list):
                    formatted = []
                    for item in data:
                        itype = item.get('type', 'purchase')
                        if itype not in ('repair', 'purchase'):
                            itype = 'purchase'
                        name = item.get('name', '').strip()
                        if not name:
                            continue
                        qty = int(item.get('qty', 1))
                        formatted.append({
                            'type': itype,
                            'name': name,
                            'qty': qty
                        })
                    return formatted
    return None

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

@router.message(F.text.in_(["Avtolar 🚗", "Автолар 🚗"]))
async def show_all_vehicles(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Сизда ушбу командани бажариш uchun huquq yo'q.")
        return
        
    vehicles = await db.get_all_vehicles()
    if not vehicles:
        await message.answer("Тизимда бирорта ҳам автоулов топилмади.")
        return
        
    await message.answer(
        "🚗 **Тизимдаги барча автолар рўйхати:**\n"
        "Тафсилотларни кўриш yoki zayavka ochish uchun mashinani tanlang:",
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
            
    status_emoji = "🔴 Носоз ҳолат" if veh_status == 'nosoz' else "🟢 Соз ҳолат"
    
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
        text += "✅ <i>Ушбу машинани таъмирлаш бўйича заявка мавжуд эмас.</i>\n\n"
        
    if history_requests:
        text += "📋 <b>Охирги таъмирлаш тарихи (максимум 5 та):</b>\n"
        for r in history_requests:
            closed_date = r['updated_at'][:16].replace('T', ' ') if r['updated_at'] else "—"
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
            "Тафсилотларни кўриш yoki zayavka ochish uchun mashinani tanlang:",
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
    if message.text == "Бекор қилиш ❌":
        user = await db.get_user(message.from_user.id)
        await state.clear()
        await message.answer("Заявка бекор қилинди.", reply_markup=get_main_keyboard(user['role']))
        return
        
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.text == "Расм йўқ 🚫":
        photo_id = None
    else:
        await message.answer("Илтимос, расм юборинг yoki 'Расм йўқ 🚫' tugmasini bosing:")
        return

    await state.update_data(old_part_photo=photo_id)
    await state.set_state(RequestCreationStates.waiting_for_items_text)
    
    cancel_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Бекор қилиш ❌")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(
        "📝 **Заявка таркибидаги маҳсулотлар ва таъмирlashlarni yozing:**\n"
        "Масалан:\n"
        "- `2 ta balon`\n"
        "- `4 ta pachivnik`\n"
        "- `generatorni sozlash`\n\n"
        "(Hammasini bitta xabarda yozishingiz mumkin, tizim avtomatik ajratadi)",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )

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
    parsed_items = await parse_request_text(text)
    
    if not parsed_items:
        await message.answer(
            "❌ Маҳсулотларни аниқлаб бўлмади. Қўлда киритиш uchun quyidagi tugmani bosing:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ Qo'lda kiritish", callback_data="itemloop_add")]
            ])
        )
        return
        
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
        async with aiosqlite.connect(db.DB_PATH) as conn:
            await conn.execute("DELETE FROM request_items WHERE request_id = ?", (editing_request_id,))
            await conn.commit()
            
        await db.add_request_item(
            request_id=editing_request_id,
            item_name=f"{prefix}{item['name']}",
            quantity_requested=item['qty'],
            quantity_available=0,
            quantity_missing=item['qty']
        )
        created_request_ids.append(editing_request_id)
        
        admin_prefix = f"🔔 **Заявка №{editing_request_id} таҳрирланиб, қайта тасдиқлашга келди!**\n\n"
        summary_text = (
            f"📝 **Заявка №{editing_request_id} муваффақиятли таҳрирланди ва қайта тасдиқлашга юборилди! 📝**\n\n"
            f"🚗 **Машина:** {vehicle_name}\n"
            f"👤 **Юборувчи:** {user['full_name']}\n\n"
            f"📋 **Заявка таркиби:**\n"
            f"   1. " + ("🛠 [Таъмирлаш] " if item_type == 'repair' else "🛒 [Сотиб олиш] ") + f"{item['name']} — {item['qty']} та\n"
        )
        
        managers = await db.get_users_by_role('manager')
        super_admins = await db.get_users_by_role('super_admin')
        all_admins = list(managers) + list(super_admins)
        for admin in all_admins:
            try:
                from main import bot
                kb = get_request_manage_keyboard(editing_request_id)
                msg_text = admin_prefix + summary_text
                if photo_id:
                    await bot.send_photo(admin['telegram_id'], photo=photo_id, caption=msg_text, reply_markup=kb, parse_mode="Markdown")
                else:
                    await bot.send_message(admin['telegram_id'], text=msg_text, reply_markup=kb, parse_mode="Markdown")
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
            
            admin_prefix = f"🔔 **Янги заявка тасдиқлаш учун келди! (№{request_id})**\n\n"
            summary_text = (
                f"📝 **Заявка №{request_id} яратилди ва тасдиқлашга юборилди!**\n\n"
                f"🚗 **Машина:** {vehicle_name}\n"
                f"👤 **Юборувчи:** {user['full_name']}\n\n"
                f"📋 **Заявка таркиби:**\n"
                f"   1. " + ("🛠 [Таъмирлаш] " if item_type == 'repair' else "🛒 [Сотиб олиш] ") + f"{item['name']} — {item['qty']} та\n"
            )
            
            managers = await db.get_users_by_role('manager')
            super_admins = await db.get_users_by_role('super_admin')
            all_admins = list(managers) + list(super_admins)
            for admin in all_admins:
                try:
                    from main import bot
                    kb = get_request_manage_keyboard(request_id)
                    msg_text = admin_prefix + summary_text
                    if photo_id:
                        await bot.send_photo(admin['telegram_id'], photo=photo_id, caption=msg_text, reply_markup=kb, parse_mode="Markdown")
                    else:
                        await bot.send_message(admin['telegram_id'], text=msg_text, reply_markup=kb, parse_mode="Markdown")
                except Exception as e:
                    print(f"Admin {admin['telegram_id']}ni ogohlantirishda xato: {e}")
                    
    status_desc = "Янги заявкалар: " + ", ".join(f"№{rid}" for rid in created_request_ids)
    await db.update_vehicle_status(vehicle_name, 'nosoz', status_desc)
    await state.clear()
    
    summary_text = (
        f"🎉 **Заявкалар муваффақиятли яратилди ва тасдиқлашга юборилди!**\n\n"
        f"🚗 **Машина:** {vehicle_name}\n"
        f"🔢 **Яратилган заявка ID'лари:** " + ", ".join(f"**№{rid}**" for rid in created_request_ids) + "\n\n"
        f"📋 **Умумий таркиб:**\n"
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
            parse_mode="Markdown"
        )
    else:
        await callback.message.answer(
            summary_text,
            reply_markup=get_main_keyboard(user['role']),
            parse_mode="Markdown"
        )

@router.message(F.text.in_(["Mening zayavkalarim 📂", "Менинг заявкаларим 📂"]))
async def show_my_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Сизда заявкаларни кўриш ҳуқуқи йўқ.")
        return
        
    my_reqs = await db.get_my_requests(message.from_user.id)
    if not my_reqs:
        await message.answer("Сизда faol (yakunlanmagan) zayavkalar mavjud emas.")
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
