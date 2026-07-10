from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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

@router.message(F.text == "Tasdiqlash kutilayotganlar 👥")
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
    if not user or user['role'] not in ['super_admin', 'observer']:
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
    for u in users:
        role_label = "Super Admin 👑" if u['role'] == 'super_admin' else ROLE_LABELS.get(u['role'], u['role'])
        text += (
            f"👤 **{u['full_name']}**\n"
            f"📞 Telefon: {u['phone']}\n"
            f"🔑 Rol: {role_label}\n"
            f"🆔 ID: `{u['telegram_id']}`\n"
            f"-------------------\n"
        )
    
    # Telegram xabar uzunligi limiti (4096 belgi) uchun bo'lib yuborish
    if len(text) > 4000:
        for x in range(0, len(text), 4000):
            await message.answer(text[x:x+4000], parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")
