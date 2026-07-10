from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database as db

router = Router()

STATUS_LABELS = {
    'pending_approval': 'Tasdiqlash kutilmoqda ⏳',
    'pending_admin_approval': 'Boshqaruvchi tasdiqlagan (Admin kutilmoqda) ⏳',
    'approved': 'Tasdiqlangan (Kuryer kutilmoqda) 🚚',
    'delivering': 'Yo\'lda 🛣️',
    'completed': 'Qabul qilindi va yakunlandi ✅',
    'rejected': 'Rad etildi ❌'
}

def get_request_manage_keyboard(request_id: int, is_admin: bool = False):
    prefix = "req_admin_" if is_admin else "req_"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Tasdiqlash ✅", callback_data=f"{prefix}approve_{request_id}"),
            InlineKeyboardButton(text="Rad etish ❌", callback_data=f"{prefix}reject_{request_id}")
        ]
    ])

@router.message(F.text == "Tasdiqlash kutilayotgan zayavkalar 📥")
async def list_pending_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['manager', 'super_admin']:
        await message.answer("Sizda ushbu komandani bajarish uchun huquq yo'q.")
        return
        
    is_admin = (user['role'] == 'super_admin')
    status_to_fetch = 'pending_admin_approval' if is_admin else 'pending_approval'
    
    pending = await db.get_requests_by_status(status_to_fetch)
    if not pending:
        msg_text = "Hozirda tasdiqlashingiz kutilayotgan zayavkalar yo'q."
        await message.answer(msg_text)
        return
        
    for r in pending:
        # Zayavka ichidagi mahsulotlarni olamiz
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += (
                f"   • **{item['item_name']}** — So'ralgan: {item['quantity_requested']} dona | "
                f"Omborda: {item['quantity_available']} | "
                f"Yetishmaydi: {item['quantity_missing']}\n"
            )
            
        text = (
            f"📝 **Zayavka №{r['id']}**\n"
            f"👤 **Yaratuvchi:** {r['creator_name']} (ID: {r['created_by']})\n"
            f"📋 **Tavsif:** {r['description']}\n\n"
            f"🔍 **Mahsulotlar tarkibi:**\n{items_text}\n"
            f"📅 **Yaratilgan vaqt:** {r['created_at'][:19].replace('T', ' ')}"
        )
        await message.answer(
            text, 
            reply_markup=get_request_manage_keyboard(r['id'], is_admin=is_admin),
            parse_mode="Markdown"
        )

@router.callback_query(F.data.startswith("req_approve_"))
async def approve_request(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'manager':
        await callback.answer("Sizda zayavkani tasdiqlash huquqi yo'q!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Zayavka topilmadi.")
        await callback.message.delete()
        return
        
    # Statusni 'pending_admin_approval' ga o'zgartirish (Admin kutilmoqda)
    await db.update_request_status(request_id, 'pending_admin_approval', callback.from_user.id, 'manager')
    await callback.answer("Zayavka tasdiqlandi va Super Adminga yuborildi.")
    
    # Zayavka tarkibi
    items = await db.get_request_items(request_id)
    items_text = ""
    for item in items:
        items_text += (
            f"   • **{item['item_name']}** — So'ralgan: {item['quantity_requested']} dona | "
            f"Omborda: {item['quantity_available']} | "
            f"Yetishmaydi (Olinadi): {item['quantity_missing']}\n"
        )
        
    summary = (
        f"✅ **Zayavka №{request_id} boshqaruvchi tomonidan tasdiqlandi (Admin kutilmoqda).**\n"
        f"📋 Tavsif: {req['description']}\n"
        f"👤 Tasdiqladi: {user['full_name']}\n\n"
        f"🔍 **Mahsulotlar tarkibi:**\n{items_text}"
    )
    
    await callback.message.edit_text(
        summary,
        reply_markup=None,
        parse_mode="Markdown"
    )
    
    # Super adminlarni avtomatik ogohlantirish
    super_admins = await db.get_users_by_role('super_admin')
    for sa in super_admins:
        try:
            from main import bot
            await bot.send_message(
                sa['telegram_id'],
                f"🔔 **Yangi zayavka Admin tasdiqlovi uchun keldi! (№{request_id})**\n"
                f"Boshqaruvchi {user['full_name']} tasdiqladi.\n\n"
                f"Mexanik/Brigadir: {req['creator_name']}\n"
                f"📋 Tavsif: {req['description']}\n\n"
                f"🔍 **Mahsulotlar tarkibi:**\n{items_text}\n"
                f"Tasdiqlash uchun 'Tasdiqlash kutilayotgan zayavkalar 📥' menyusidan foydalaning."
            )
        except Exception as e:
            print(f"Super adminni ogohlantirishda xato: {e}")

@router.callback_query(F.data.startswith("req_admin_approve_"))
async def admin_approve_request(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'super_admin':
        await callback.answer("Sizda zayavkani yakuniy tasdiqlash huquqi yo'q!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[3])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Zayavka topilmadi.")
        await callback.message.delete()
        return
        
    # Statusni 'approved' ga o'zgartirish (Kuryer kutilmoqda)
    await db.update_request_status(request_id, 'approved', callback.from_user.id, 'super_admin')
    await callback.answer("Zayavka yakuniy tasdiqlandi va yetkazib beruvchilarga yuborildi.")
    
    # Zayavka tarkibi
    items = await db.get_request_items(request_id)
    items_text = ""
    for item in items:
        items_text += (
            f"   • **{item['item_name']}** — So'ralgan: {item['quantity_requested']} dona | "
            f"Omborda: {item['quantity_available']} | "
            f"Yetishmaydi (Olinadi): {item['quantity_missing']}\n"
        )
        
    summary = (
        f"👑 **Zayavka №{request_id} Super Admin tomonidan tasdiqlandi va yetkazishga yuborildi.**\n"
        f"📋 Tavsif: {req['description']}\n"
        f"👤 Tasdiqladi: {user['full_name']} (Super Admin)\n\n"
        f"🔍 **Mahsulotlar tarkibi:**\n{items_text}"
    )
    
    await callback.message.edit_text(
        summary,
        reply_markup=None,
        parse_mode="Markdown"
    )
    
    # Yetkazib beruvchilarni (Kuryer) avtomatik ogohlantirish
    couriers = await db.get_users_by_role('courier')
    for c in couriers:
        try:
            from main import bot
            await bot.send_message(
                c['telegram_id'],
                f"🚚 **Yangi buyurtma (Zayavka №{request_id}) yetkazish uchun keldi!**\n\n"
                f"Mexanik/Brigadir: {req['creator_name']}\n"
                f"📋 Tavsif: {req['description']}\n\n"
                f"🔍 **Olib kelinadigan tovarlar (Yetishmayotgan qoldiq):**\n{items_text}\n"
                f"Yetkazishni qabul qilish uchun pastdagi kuryer menyusidan foydalaning."
            )
        except Exception as e:
            print(f"Kuryerni ogohlantirishda xato: {e}")

    # Yaratuvchini (Mexanik/Brigadir) ogohlantirish
    try:
        from main import bot
        await bot.send_message(
            req['created_by'],
            f"✅ Sizning №{request_id}-sonli zayavkangiz yakuniy tasdiqlandi va kuryerlarga yuborildi."
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")

@router.callback_query(F.data.startswith("req_reject_"))
async def reject_request(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'manager':
        await callback.answer("Sizda zayavkani rad etish huquqi yo'q!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Zayavka topilmadi.")
        await callback.message.delete()
        return
        
    await db.update_request_status(request_id, 'rejected', callback.from_user.id, 'manager')
    await callback.answer("Zayavka rad etildi.")
    await callback.message.edit_text(
        f"❌ **Zayavka №{request_id} boshqaruvchi tomonidan rad etildi.**\n"
        f"📋 Tavsif: {req['description']}\n"
        f"👤 Rad etdi: {user['full_name']}",
        reply_markup=None,
        parse_mode="Markdown"
    )
    
    # Yaratuvchini ogohlantirish
    try:
        from main import bot
        await bot.send_message(
            req['created_by'],
            f"❌ Afsuski, sizning №{request_id}-sonli zayavkangiz boshqaruvchi tomonidan rad etildi."
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")

@router.callback_query(F.data.startswith("req_admin_reject_"))
async def admin_reject_request(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] != 'super_admin':
        await callback.answer("Sizda zayavkani rad etish huquqi yo'q!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[3])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Zayavka topilmadi.")
        await callback.message.delete()
        return
        
    await db.update_request_status(request_id, 'rejected', callback.from_user.id, 'super_admin')
    await callback.answer("Zayavka rad etildi.")
    await callback.message.edit_text(
        f"❌ **Zayavka №{request_id} Super Admin tomonidan rad etildi.**\n"
        f"📋 Tavsif: {req['description']}\n"
        f"👤 Rad etdi: {user['full_name']}",
        reply_markup=None,
        parse_mode="Markdown"
    )
    
    # Yaratuvchini ogohlantirish
    try:
        from main import bot
        await bot.send_message(
            req['created_by'],
            f"❌ Afsuski, sizning №{request_id}-sonli zayavkangiz Super Admin tomonidan rad etildi."
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")

@router.message(F.text == "Barcha zayavkalar 📝")
async def show_all_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager', 'observer', 'warehouseman']:
        await message.answer("Sizda zayavkalarni ko'rish huquqi yo'q.")
        return
        
    requests = await db.get_all_requests()
    if not requests:
        await message.answer("Tizimda hech qanday zayavka yo'q.")
        return
        
    await message.answer("📝 **Zayavkalar ro'yxati (oxirgi 10 ta):**")
    
    for r in requests[:10]:
        status_label = STATUS_LABELS.get(r['status'], r['status'])
        
        # Mahsulotlarni olamiz
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += f"   • {item['item_name']}: {item['quantity_requested']} ta (Yetishmaydi: {item['quantity_missing']})\n"
            
        text = (
            f"🆔 **Zayavka №{r['id']}**\n"
            f"👤 Yaratuvchi: {r['creator_name']}\n"
            f"📋 Tavsif: {r['description']}\n"
            f"⚙️ Holati: {status_label}\n"
            f"🔍 Mahsulotlar:\n{items_text}"
            f"📅 Sana: {r['created_at'][:16].replace('T', ' ')}"
        )
        
        # Boshqaruvchi uchun tasdiqlash tugmalari (agar status pending_approval bo'lsa)
        # Super Admin uchun tasdiqlash tugmalari (agar status pending_admin_approval bo'lsa)
        reply_markup = None
        if user['role'] == 'manager' and r['status'] == 'pending_approval':
            reply_markup = get_request_manage_keyboard(r['id'], is_admin=False)
        elif user['role'] == 'super_admin' and r['status'] == 'pending_admin_approval':
            reply_markup = get_request_manage_keyboard(r['id'], is_admin=True)
            
        await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown")
