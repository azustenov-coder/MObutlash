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
            InlineKeyboardButton(text="Tasdiqlash ✅", callback_data=f"approve_{telegram_id}"),
            InlineKeyboardButton(text="Rad etish ❌", callback_data=f"reject_{telegram_id}")
        ]
    ])

@router.message(F.text == "A'zolik so'rovlari 👥")
async def show_pending_users(message: Message):
    # Foydalanuvchi admin ekanligini tekshiramiz
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] != 'super_admin':
        await message.answer("Sizda ushbu komandani bajarish uchun huquq yo'q.")
        return
        
    pending = await db.get_pending_users()
    if not pending:
        await message.answer("Hozirda tasdiqlash kutilayotgan foydalanuvchilar yo'q.")
        return
        
    for u in pending:
        role_label = ROLE_LABELS.get(u['role'], u['role'])
        text = (
            f"👤 **Foydalanuvchi:** {u['full_name']}\n"
            f"📞 **Telefon:** {u['phone']}\n"
            f"🔑 **So'ralgan rol:** {role_label}\n"
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
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return
        
    user_id = int(callback.data.split("_")[1])
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("Foydalanuvchi topilmadi.")
        await callback.message.delete()
        return
        
    await db.approve_user(user_id)
    await callback.answer(f"{user['full_name']} tasdiqlandi.")
    
    role_label = ROLE_LABELS.get(user['role'], user['role'])
    await callback.message.edit_text(
        f"✅ {user['full_name']} tasdiqlandi.\nRol: {role_label}",
        reply_markup=None
    )
    
    # Foydalanuvchiga xabar yuborish
    try:
        from main import bot
        await bot.send_message(
            user_id,
            f"🎉 Tabriklaymiz! Sizning so'rovingiz tasdiqlandi.\n"
            f"Sizga **{role_label}** roli berildi.",
            reply_markup=get_main_keyboard(user['role']),
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Foydalanuvchini ogohlantirishda xato (tasdiqlash): {e}")

@router.callback_query(F.data.startswith("reject_"))
async def process_reject(callback: CallbackQuery):
    admin = await db.get_user(callback.from_user.id)
    if not admin or admin['role'] != 'super_admin':
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return
        
    user_id = int(callback.data.split("_")[1])
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("Foydalanuvchi topilmadi.")
        await callback.message.delete()
        return
        
    await db.reject_user(user_id)
    await callback.answer(f"{user['full_name']} rad etildi.")
    await callback.message.edit_text(
        f"❌ {user['full_name']} so'rovi rad etildi va ro'yxatdan o'chirildi.",
        reply_markup=None
    )
    
    # Foydalanuvchiga xabar yuborish
    try:
        from main import bot
        await bot.send_message(
            user_id,
            "Afsuski, sizning ro'yxatdan o'tish so'rovingiz admin tomonidan rad etildi."
        )
    except Exception as e:
        print(f"Foydalanuvchini ogohlantirishda xato (rad etish): {e}")

@router.message(F.text == "Foydalanuvchilar ro'yxati 📋")
async def show_users_list(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'observer', 'manager']:
        await message.answer("Sizda ushbu ma'lumotni ko'rish huquqi yo'q.")
        return
        
    # Barcha tasdiqlangan foydalanuvchilarni ko'rsatish
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute("SELECT * FROM users WHERE is_approved = 1 ORDER BY role") as cursor:
            users = await cursor.fetchall()
            
    if not users:
        await message.answer("Tizimda tasdiqlangan foydalanuvchilar yo'q.")
        return
        
    text = "📋 **Tasdiqlangan foydalanuvchilar ro'yxati:**\n\n"
    keyboard_buttons = []
    
    for u in users:
        role_label = "Super Admin 👑" if u['role'] == 'super_admin' else ROLE_LABELS.get(u['role'], u['role'])
        text += (
            f"👤 **{u['full_name']}**\n"
            f"📞 Telefon: {u['phone']}\n"
            f"🔑 Rol: {role_label}\n"
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
        await callback.answer("Sizda xabar yuborish huquqi yo'q!", show_alert=True)
        return
        
    target_id = int(callback.data.split("_")[2])
    target_user = await db.get_user(target_id)
    if not target_user:
        await callback.answer("Foydalanuvchi topilmadi.")
        return
        
    await state.update_data(target_id=target_id, target_name=target_user['full_name'])
    await state.set_state(AdminMessageStates.waiting_for_message)
    
    role_label = ROLE_LABELS.get(target_user['role'], target_user['role'])
    if target_user['role'] == 'super_admin':
        role_label = "Super Admin 👑"
        
    await callback.message.answer(
        f"✍️ **{target_user['full_name']}** ({role_label}) uchun xabaringizni yozing:\n"
        f"Matn, rasm, video yoki fayl yuborishingiz mumkin.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Bekor qilish ❌", callback_data="cancel_write")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "cancel_write")
async def cancel_writing(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Xabar yuborish bekor qilindi.", reply_markup=None)
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
            f"🔔 **{sender_name}** ({sender_role}) dan yangi xabar keldi:\n"
            f"----------------------------------------"
        )
        # Xabarning to'liq nusxasini ko'chirib yuboramiz
        await message.send_copy(chat_id=target_id)
        
        await message.answer(
            f"✅ Xabaringiz **{target_name}**ga muvaffaqiyatli yuborildi!",
            reply_markup=get_main_keyboard(sender['role'])
        )
        await state.clear()
    except Exception as e:
        await message.answer(
            f"❌ Xabarni yuborishda xatolik yuz berdi: {e}\n"
            f"Foydalanuvchi botni to'xtatgan bo'lishi mumkin.",
            reply_markup=get_main_keyboard(sender['role'])
        )
        await state.clear()
