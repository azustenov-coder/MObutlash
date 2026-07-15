from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
import database as db
from handlers.common import get_main_keyboard, ROLE_LABELS

router = Router()

class UserManagementStates(StatesGroup):
    waiting_for_search_query = State()
    viewing_user = State()

async def is_super_admin(message: Message) -> bool:
    user = await db.get_user(message.from_user.id)
    return user is not None and user['role'] == 'super_admin'

async def is_super_admin_callback(callback: CallbackQuery) -> bool:
    user = await db.get_user(callback.from_user.id)
    return user is not None and user['role'] == 'super_admin'

@router.message(F.text.in_(["Foydalanuvchilar ro'yxati 📋", "Ходимлар рўйхати 📋"]) | F.text.startswith("Foydalanuvchilar ro'yxati 📋") | F.text.startswith("Ходимлар рўйхати 📋"), is_super_admin)
async def handle_user_mgmt_entry(message: Message, state: FSMContext):
    await state.clear()
    await show_usermgmt_main(message, state)

async def show_usermgmt_main(message: Message, state: FSMContext):
    await state.set_state(UserManagementStates.waiting_for_search_query)
    
    text = (
        "👥 **Ходимларни бошқариш панели**\n\n"
        "Қуйидаги тугмалардан бирини танланг ёки қидирмоқчи бўлган ходимнинг исмини/телефон рақамини ёзинг:"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Барча ходимlar", callback_data="usermgmt_list_approved"),
            InlineKeyboardButton(text="⏳ Кутаётганлар", callback_data="usermgmt_list_pending")
        ],
        [InlineKeyboardButton(text="❌ Ёпиш", callback_data="usermgmt_close")]
    ])
    
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "usermgmt_main", is_super_admin_callback)
async def callback_usermgmt_main(callback: CallbackQuery, state: FSMContext):
    await show_usermgmt_main(callback, state)
    await callback.answer()

@router.callback_query(F.data == "usermgmt_close", is_super_admin_callback)
async def callback_usermgmt_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    await callback.message.delete()
    await callback.message.answer("Бошқариш панели ёпилди.", reply_markup=get_main_keyboard(user['role']))
    await callback.answer()

@router.callback_query(F.data == "usermgmt_list_approved", is_super_admin_callback)
async def callback_list_approved(callback: CallbackQuery, state: FSMContext):
    users = await db.get_approved_users()
            
    if not users:
        await callback.answer("Тасдиқланган ходимлар йўқ.", show_alert=True)
        return
        
    text = "📋 **Тасдиқланган ходимлар рўйхати:**\n\nБошқариш учун ходимни танланг:"
    
    keyboard = []
    for u in users:
        role_label = "Super Admin" if u['role'] == 'super_admin' else ROLE_LABELS.get(u['role'], u['role'])
        keyboard.append([InlineKeyboardButton(text=f"👤 {u['full_name']} ({role_label})", callback_data=f"usermgmt_view_{u['telegram_id']}")])
        
    keyboard.append([InlineKeyboardButton(text="🔙 Орқага", callback_data="usermgmt_main")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "usermgmt_list_pending", is_super_admin_callback)
async def callback_list_pending(callback: CallbackQuery, state: FSMContext):
    pending = await db.get_pending_users()
    if not pending:
        await callback.answer("Кутаётган аъзолик сўровлари йўқ.", show_alert=True)
        return
        
    text = "⏳ **Аъзоликни кутаётган ходимлар:**\n\nБошқариш ёки тасдиқлаш учун танланг:"
    
    keyboard = []
    for u in pending:
        keyboard.append([InlineKeyboardButton(text=f"⏳ {u['full_name']} ({u['phone']})", callback_data=f"usermgmt_view_{u['telegram_id']}")])
        
    keyboard.append([InlineKeyboardButton(text="🔙 Орқага", callback_data="usermgmt_main")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.message(UserManagementStates.waiting_for_search_query, is_super_admin)
async def process_user_search(message: Message, state: FSMContext):
    query = message.text.strip()
    if query in ["Бекор қилиш ❌", "Bekor qilish", "/cancel", "/start", "/menu"]:
        user = await db.get_user(message.from_user.id)
        await state.clear()
        await message.answer("Бошқариш панели ёпилди.", reply_markup=get_main_keyboard(user['role']))
        return
        
    results = await db.search_users(query)
            
    if not results:
        await message.answer(
            f"🔍 «{query}» бўйича ҳеч қандай ходим топилмади.\n"
            "Қайтадан уриниб кўринг ёки бошқа исм ёзинг:"
        )
        return
        
    text = f"🔍 **Қидирув натижалари ('{query}'):**\n\nБошқариш учун ходимни танланг:"
    keyboard = []
    for u in results:
        role_label = "Super Admin" if u['role'] == 'super_admin' else ROLE_LABELS.get(u['role'], u['role'])
        status_prefix = "👤" if u['is_approved'] == 1 else "⏳"
        keyboard.append([InlineKeyboardButton(text=f"{status_prefix} {u['full_name']} ({role_label})", callback_data=f"usermgmt_view_{u['telegram_id']}")])
        
    keyboard.append([InlineKeyboardButton(text="🔙 Орқага", callback_data="usermgmt_main")])
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

async def show_user_profile(callback: CallbackQuery, telegram_id: int, state: FSMContext):
    u = await db.get_user(telegram_id)
    if not u:
        await callback.answer("Фойдаланувчи топилмади.", show_alert=True)
        return
        
    role_label = "Super Admin" if u['role'] == 'super_admin' else ROLE_LABELS.get(u['role'], u['role'])
    status_text = "Тасдиқланган ✅" if u['is_approved'] == 1 else "Кутмоқда ⏳"
    
    text = (
        f"👤 **Ходим маълумотлари:**\n\n"
        f"🔸 **Исми:** {u['full_name']}\n"
        f"📞 **Телефон:** {u['phone']}\n"
        f"🔑 **Роли:** {role_label}\n"
        f"🆔 **Telegram ID:** `{u['telegram_id']}`\n"
        f"⚙️ **Ҳолати:** {status_text}\n"
        f"📅 **Рўйхатдан ўтган:** {db.format_datetime(u['created_at'])}\n"
    )
    
    keyboard = []
    # Super Admin hisobini o'chirib yuborish yoki uning rolini almashtirish mumkin emas.
    if u['telegram_id'] != callback.from_user.id and u['role'] != 'super_admin':
        keyboard.append([
            InlineKeyboardButton(text="⚙️ Ролни ўзгартириш", callback_data=f"usermgmt_changerole_{telegram_id}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="❌ Тизимдан ўчириш", callback_data=f"usermgmt_delconfirm_{telegram_id}")
        ])
        
    keyboard.append([InlineKeyboardButton(text="🔙 Орқага", callback_data="usermgmt_list_approved")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("usermgmt_view_"), is_super_admin_callback)
async def callback_view_user(callback: CallbackQuery, state: FSMContext):
    telegram_id = int(callback.data.split("_")[2])
    await show_user_profile(callback, telegram_id, state)
    await callback.answer()

@router.callback_query(F.data.startswith("usermgmt_changerole_"), is_super_admin_callback)
async def callback_changerole(callback: CallbackQuery, state: FSMContext):
    telegram_id = int(callback.data.split("_")[2])
    
    text = "⚙️ **Янги ролни танланг:**"
    keyboard = []
    
    for r_key, r_label in ROLE_LABELS.items():
        keyboard.append([InlineKeyboardButton(text=r_label, callback_data=f"usermgmt_setrole_{telegram_id}_{r_key}")])
        
    keyboard.append([InlineKeyboardButton(text="🔙 Бекор қилиш", callback_data=f"usermgmt_view_{telegram_id}")])
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("usermgmt_setrole_"), is_super_admin_callback)
async def callback_setrole(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    telegram_id = int(parts[2])
    role_key = parts[3]
    
    u = await db.get_user(telegram_id)
    if not u or u['telegram_id'] == callback.from_user.id or u['role'] == 'super_admin' or role_key not in ROLE_LABELS:
        await callback.answer("Bu akkaunt rolini o'zgartirib bo'lmaydi.", show_alert=True)
        return

    await db.update_user_role(telegram_id, role_key)
    
    u = await db.get_user(telegram_id)
    if u and u['is_approved'] == 0:
        await db.approve_user(telegram_id, role_key)
        
    role_label = ROLE_LABELS.get(role_key, role_key)
    await callback.answer(f"Муваффақиятли ўзгартирилди: {role_label}", show_alert=True)
    
    try:
        from main import bot
        msg_text = f"🔔 **Сизнинг ролингиз Super Admin томонидан ўзгартирилди!**\n🔑 **Янги ролингиз:** {role_label}"
        await bot.send_message(
            chat_id=telegram_id,
            text=msg_text,
            reply_markup=get_main_keyboard(role_key)
        )
    except Exception as e:
        print(f"Failed to notify user {telegram_id} about role change: {e}")
        
    await show_user_profile(callback, telegram_id, state)

@router.callback_query(F.data.startswith("usermgmt_delconfirm_"), is_super_admin_callback)
async def callback_delconfirm(callback: CallbackQuery, state: FSMContext):
    telegram_id = int(callback.data.split("_")[2])
    u = await db.get_user(telegram_id)
    if not u or u['telegram_id'] == callback.from_user.id or u['role'] == 'super_admin':
        await callback.answer("Bu akkauntni o'chirib bo'lmaydi.", show_alert=True)
        return
    text = f"⚠️ **Ҳақиқатан ҳам {u['full_name']}ни тизимдан ўчириб юбормоқчисиз?**"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Ҳа, ўчирилсин", callback_data=f"usermgmt_delete_{telegram_id}"),
            InlineKeyboardButton(text="🟢 Йўқ, bekor qilish", callback_data=f"usermgmt_view_{telegram_id}")
        ]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("usermgmt_delete_"), is_super_admin_callback)
async def callback_delete(callback: CallbackQuery, state: FSMContext):
    telegram_id = int(callback.data.split("_")[2])
    u = await db.get_user(telegram_id)
    if not u or u['telegram_id'] == callback.from_user.id or u['role'] == 'super_admin':
        await callback.answer("Bu akkauntni o'chirib bo'lmaydi.", show_alert=True)
        return
    await db.reject_user(telegram_id)
    await callback.answer("Фойдаланувчи ўчирилди.", show_alert=True)
    
    try:
        from main import bot
        await bot.send_message(
            chat_id=telegram_id,
            text="🔔 **Сизнинг аккаунтингиз Super Admin томонидан тизимдан ўчирилди.**",
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        print(f"Failed to notify user {telegram_id} about deletion: {e}")
        
    await show_usermgmt_main(callback, state)
