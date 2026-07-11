from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import database as db
from handlers.common import ROLE_LABELS, get_main_keyboard

router = Router()

def get_approve_keyboard(telegram_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Тасдиқлаш ✅", callback_data=f"approve_{telegram_id}"),
            InlineKeyboardButton(text="Рад этиш ❌", callback_data=f"reject_{telegram_id}")
        ]
    ])

@router.message(F.text.in_(["A'zolik so'rovlari 👥", "Аъзолик сўровлари 👥"]))
async def show_pending_users(message: Message):
    # Foydalanuvchi admin ekanligini tekshiramiz
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'super_admin':
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    pending = await db.get_pending_users()
    if not pending:
        await message.answer("Ҳозирда тасдиқлаш кутилаётган ходимлар йўқ.")
        return
        
    for u in pending:
        role_label = ROLE_LABELS.get(u['role'], u['role'])
        text = (
            f"👤 **Ходим:** {u['full_name']}\n"
            f"📞 **Телефон:** {u['phone']}\n"
            f"🔑 **Сўралган рол:** {role_label}\n"
            f"🆔 **TG ID:** `{u['telegram_id']}`"
        )
        await message.answer(
            text, 
            reply_markup=get_approve_keyboard(u['telegram_id']),
            parse_mode="Markdown"
        )

@router.callback_query(F.data.startswith("approve_"))
async def process_approve(callback: CallbackQuery):
    admin = await db.get_user(callback.from_user.id)
    if not admin or admin['role'] != 'super_admin':
        await callback.answer("Рухсат берилмаган!", show_alert=True)
        return
        
    user_id = int(callback.data.split("_")[1])
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("Ходим топилмади.")
        await callback.message.delete()
        return
        
    await db.approve_user(user_id)
    await callback.answer(f"{user['full_name']} тасдиқланди.")
    
    role_label = ROLE_LABELS.get(user['role'], user['role'])
    await callback.message.edit_text(
        f"✅ {user['full_name']} тасдиқланди.\nРол: {role_label}",
        reply_markup=None
    )
    
    # Foydalanuvchiga xabar yuborish
    try:
        from main import bot
        await bot.send_message(
            user_id,
            f"🎉 Табриклаймиз! Сизнинг сўровингиз тасдиқланди.\n"
            f"Сизга **{role_label}** роли берилди.",
            reply_markup=get_main_keyboard(user['role']),
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Foydalanuvchini ogohlantirishda xato (tasdiqlash): {e}")

@router.callback_query(F.data.startswith("reject_"))
async def process_reject(callback: CallbackQuery):
    admin = await db.get_user(callback.from_user.id)
    if not admin or admin['role'] != 'super_admin':
        await callback.answer("Рухсат берилмаган!", show_alert=True)
        return
        
    user_id = int(callback.data.split("_")[1])
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("Ходим топилмади.")
        await callback.message.delete()
        return
        
    await db.reject_user(user_id)
    await callback.answer(f"{user['full_name']} рад этилди.")
    await callback.message.edit_text(
        f"❌ {user['full_name']} сўрови рад этилди ва рўйхатдан ўчирилди.",
        reply_markup=None
    )
    
    # Foydalanuvchiga xabar yuborish
    try:
        from main import bot
        await bot.send_message(
            user_id,
            "Афсуски, сизнинг рўйхатдан ўтиш сўровингиз админ томонидан рад этилди."
        )
    except Exception as e:
        print(f"Foydalanuvchini ogohlantirishda xato (rad etish): {e}")

@router.message(F.text.in_(["Foydalanuvchilar ro'yxati 📋", "Ходимлар рўйхати 📋"]))
async def show_users_list(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'observer', 'manager']:
        await message.answer("Сизда ушбу маълумотни кўриш ҳуқуқи йўқ.")
        return
        
    # Barcha tasdiqlangan foydalanuvchilarni ko'rsatish
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute("SELECT * FROM users WHERE is_approved = 1 ORDER BY role") as cursor:
            users = await cursor.fetchall()
            
    if not users:
        await message.answer("Тизимда тасдиқланган ходимлар йўқ.")
        return
        
    text = "📋 **Тасдиқланган ходимлар рўйхати:**\n\n"
    keyboard_buttons = []
    
    for u in users:
        role_label = "Super Admin 👑" if u['role'] == 'super_admin' else ROLE_LABELS.get(u['role'], u['role'])
        text += (
            f"👤 **{u['full_name']}**\n"
            f"📞 Телефон: {u['phone']}\n"
            f"🔑 Рол: {role_label}\n"
            f"🆔 ID: `{u['telegram_id']}`\n"
            f"-------------------\n"
        )
        
        # Super admin va manager o'zidan boshqa hammaga xabar yubora oladi
        if user['role'] in ['super_admin', 'manager'] and u['telegram_id'] != message.from_user.id:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"✉️ {u['full_name']} ({ROLE_LABELS.get(u['role'], u['role'])[:15]})", 
                    callback_data=f"write_msg_{u['telegram_id']}"
                )
            ])
            
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons) if keyboard_buttons else None
    
    # Telegram xabar uzunligi limiti (4096 belgi) uchun bo'lib yuborish
    if len(text) > 4000:
        for x in range(0, len(text), 4000):
            is_last = (x + 4000) >= len(text)
            markup = reply_markup if is_last else None
            await message.answer(text[x:x+4000], reply_markup=markup, parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown")


class AdminMessageStates(StatesGroup):
    waiting_for_message = State()

@router.callback_query(F.data.startswith("write_msg_"))
async def start_writing_message(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager']:
        await callback.answer("Сизда хабар юбориш ҳуқуқи йўқ!", show_alert=True)
        return
        
    target_id = int(callback.data.split("_")[2])
    target_user = await db.get_user(target_id)
    if not target_user:
        await callback.answer("Ходим топилмади.")
        return
        
    await state.update_data(target_id=target_id, target_name=target_user['full_name'])
    await state.set_state(AdminMessageStates.waiting_for_message)
    
    role_label = ROLE_LABELS.get(target_user['role'], target_user['role'])
    if target_user['role'] == 'super_admin':
        role_label = "Super Admin 👑"
        
    await callback.message.answer(
        f"✍️ **{target_user['full_name']}** ({role_label}) учун хабарингизни ёзинг:\n"
        f"Матн, расм, видео ёки файл юборишингиз мумкин.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Бекор қилиш ❌", callback_data="cancel_write")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "cancel_write")
async def cancel_writing(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Хабар юбориш бекор қилинди.", reply_markup=None)
    await callback.answer()

@router.message(AdminMessageStates.waiting_for_message)
async def send_message_to_user(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get('target_id')
    target_name = data.get('target_name')
    
    sender = await db.get_user(message.from_user.id)
    sender_name = sender['full_name']
    sender_role = ROLE_LABELS.get(sender['role'], sender['role'])
    if sender['role'] == 'super_admin':
        sender_role = "Super Admin 👑"
        
    try:
        from main import bot
        # Avval ogohlantiruvchi sarlavha yuboramiz
        await bot.send_message(
            target_id,
            f"🔔 **{sender_name}** ({sender_role}) дан янги хабар келди:\n"
            f"----------------------------------------"
        )
        # Xabarning to'liq nusxasini ko'chirib yuboramiz
        await message.send_copy(chat_id=target_id)
        
        await message.answer(
            f"✅ Хабарингиз **{target_name}**га муваффақиятли юборилди!",
            reply_markup=get_main_keyboard(sender['role'])
        )
    except Exception as e:
        print(f"Xabar yuborishda xato: {e}")
        await message.answer(
            f"❌ Хабарни юборишда хатолик юз берди: {e}\n"
            f"Ходим ботни тўхтатган бўлиши мумкин.",
            reply_markup=get_main_keyboard(sender['role'])
        )
    finally:
        await state.clear()
