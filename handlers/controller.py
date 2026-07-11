from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database as db
from handlers.common import get_request_manage_keyboard

router = Router()

STATUS_LABELS = {
    'pending_approval': 'Тасдиқлаш кутилмоқда ⏳',
    'pending_admin_approval': 'Бошқарувчи тасдиқлаган (Админ кутилмоқда) ⏳',
    'approved': 'Тасдиқланган (Таъминотчи кутилмоқда) 🚚',
    'delivering': 'Йўлда 🛣️',
    'searching': 'Қидирилмоқда 🔍',
    'purchased': 'Сотиб олинди (Йўлда) 🛒',
    'waiting_receipt': 'Қабул кутилмоқда 📥',
    'ready_for_installation': 'Омборга келган (Ўрнатилиши кутилмоқда) 🛠️',
    'completed': 'Ўрнатилди ва якунланди ✅',
    'rejected': 'Рад этилди ❌'
}

@router.message(F.text.in_(["Kutilayotgan zayavkalar 📥", "Кутилаётган заявкалар 📥"]))
async def list_pending_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['manager', 'super_admin']:
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    pending = await db.get_requests_by_status('pending_approval')
    if not pending:
        msg_text = "Ҳозирда тасдиқлашингиз кутилаётган заявкалар йўқ."
        await message.answer(msg_text)
        return
        
    for r in pending:
        # Zayavka ichidagi mahsulotlarni olamiz
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += (
                f"   • <b>{item['item_name']}</b> — Сўралган: {item['quantity_requested']} дона | "
                f"Омборда: {item['quantity_available']} | "
                f"Етишмайди: {item['quantity_missing']}\n"
            )
            
        text = (
            f"📝 <b>Заявка №{r['id']}</b>\n"
            f"👤 <b>Яратувчи:</b> {r['creator_name']} (ID: {r['created_by']})\n"
            f"📋 <b>Тавсиф:</b> {r['description']}\n\n"
            f"🔍 <b>Маҳсулотлар таркиби:</b>\n{items_text}\n"
            f"📅 <b>Яратилган вақт:</b> {r['created_at'][:19].replace('T', ' ')}"
        )
        await message.answer(
            text, 
            reply_markup=get_request_manage_keyboard(r['id']),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("req_approve_"))
async def approve_request(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['manager', 'super_admin']:
        await callback.answer("Сизда заявкани тасдиқлаш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Заявка топилмади.")
        await callback.message.delete()
        return
        
    # Statusni 'approved' (Tasdiqlangan) ga o'zgartirish
    role_label = 'super_admin' if user['role'] == 'super_admin' else 'manager'
    await db.update_request_status(request_id, 'approved', callback.from_user.id, role_label)
    await callback.answer("Заявка тасдиқланди ва таъминотчиларга юборилди.")
    
    # Zayavka tarkibi
    items = await db.get_request_items(request_id)
    items_text = ""
    for item in items:
        items_text += (
            f"   • **{item['item_name']}** — So'ralgan: {item['quantity_requested']} dona | "
            f"Omborda: {item['quantity_available']} | "
            f"Yetishmaydi (Olinadi): {item['quantity_missing']}\n"
        )
        
    created_date = req['created_at'][:16].replace('T', ' ')
    role_display = "Супер Админ 👑" if user['role'] == 'super_admin' else "Бошқарувчи 💼"
    summary = (
        f"✅ **Заявка №{request_id} {role_display} томонидан тасдиқланди ва етказишга юборилди.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 **Сана:** {created_date}\n"
        f"👤 Тасдиқлади: {user['full_name']}\n\n"
        f"🔍 **Маҳсулотлар таркиби:**\n{items_text}"
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
    
    # Ta'minotchilarni (Kuryer) avtomatik ogohlantirish (bilan birga rasm va inline tugmalar yuboriladi)
    from handlers.common import get_courier_take_keyboard
    couriers = await db.get_users_by_role('courier')
    for c in couriers:
        try:
            from main import bot
            msg_text = (
                f"🚚 **Янги буюртма (Заявка №{request_id}) етказиш учун келди!**\n\n"
                f"Механик/Бригадир: {req['creator_name']}\n"
                f"📋 Тавсиф: {req['description']}\n"
                f"📅 **Сана:** {created_date}\n\n"
                f"🔍 **Олиб келинадиган товарлар (Етишмаётган қолдиқ):**\n{items_text}\n"
                f"Етказишни қабул қилиш учун пастдаги тугмани босинг."
            )
            kb = get_courier_take_keyboard(request_id)
            if req['old_part_photo']:
                await bot.send_photo(
                    c['telegram_id'],
                    photo=req['old_part_photo'],
                    caption=msg_text,
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
            else:
                await bot.send_message(
                    c['telegram_id'],
                    text=msg_text,
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
        except Exception as e:
            print(f"Ta'minotchini ogohlantirishda xato: {e}")
            
    # Yaratuvchini (Mexanik/Brigadir) ogohlantirish
    try:
        from main import bot
        await bot.send_message(
            req['created_by'],
            f"✅ Сизнинг №{request_id}-сонли заявкангиз тасдиқланди ва таъминотчиларга юборилди."
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")

@router.callback_query(F.data.startswith("req_reject_"))
async def reject_request(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['manager', 'super_admin']:
        await callback.answer("Сизда заявкани рад этиш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Заявка топилмади.")
        await callback.message.delete()
        return
        
    role_label = 'super_admin' if user['role'] == 'super_admin' else 'manager'
    await db.update_request_status(request_id, 'rejected', callback.from_user.id, role_label)
    await callback.answer("Заявка рад этилди.")
    
    created_date = req['created_at'][:16].replace('T', ' ')
    role_display = "Супер Админ 👑" if user['role'] == 'super_admin' else "Бошқарувчи 💼"
    summary_text = (
        f"❌ **Заявка №{request_id} {role_display} томонидан рад этилди.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 **Сана:** {created_date}\n"
        f"👤 Рад этди: {user['full_name']}"
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=summary_text,
            reply_markup=None,
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            summary_text,
            reply_markup=None,
            parse_mode="Markdown"
        )
        
    # Yaratuvchini ogohlantirish
    try:
        from main import bot
        await bot.send_message(
            req['created_by'],
            f"❌ Афсуски, сизнинг №{request_id}-сонли заявкангиз {role_display} томонидан рад этилди."
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")

@router.callback_query(F.data.startswith("req_revision_"))
async def process_req_revision(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['manager', 'super_admin']:
        await callback.answer("Сизда ушбу операцияни бажариш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Заявка топилмади.")
        await callback.message.delete()
        return
        
    role_label = 'super_admin' if user['role'] == 'super_admin' else 'manager'
    await db.update_request_status(request_id, 'needs_revision', callback.from_user.id, role_label)
    await callback.answer("Заявка қайта ишлашга юборилди.")
    
    created_date = req['created_at'][:16].replace('T', ' ')
    role_display = "Супер Админ 👑" if user['role'] == 'super_admin' else "Бошқарувчи 💼"
    summary_text = (
        f"🔄 **Заявка №{request_id} қайта ишлашга қайтариб юборилди.**\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 **Сана:** {created_date}\n"
        f"👤 Қайтарди: {user['full_name']}"
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=summary_text,
            reply_markup=None,
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            summary_text,
            reply_markup=None,
            parse_mode="Markdown"
        )
        
    # Yaratuvchini (Mexanik/Brigadir) ogohlantirish
    try:
        from main import bot
        from handlers.common import get_mechanic_resubmit_keyboard
        kb = get_mechanic_resubmit_keyboard(request_id)
        await bot.send_message(
            req['created_by'],
            f"🔄 **Сизнинг №{request_id}-сонли заявкангиз {role_display} томонидан қайта ишлашга қайтарилди.**\n\n"
            f"Илтимос, тафсилотларни таҳрирлаб, қайта юбориш учун қуйидаги тугмани босинг:",
            reply_markup=kb
        )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato (qayta ishlash): {e}")

@router.message(F.text.in_(["Barcha zayavkalar 📝", "Барча заявкалар 📝"]))
async def show_all_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager', 'observer', 'warehouseman']:
        await message.answer("Сизда заявкаларни кўриш ҳуқуқи йўқ.")
        return
        
    requests = await db.get_all_requests()
    if not requests:
        await message.answer("Тизимда ҳеч қандай заявка йўқ.")
        return
        
    await message.answer("📝 <b>Заявкалар рўйхати (охирги 10 та):</b>", parse_mode="HTML")
    
    for r in requests[:10]:
        status_label = STATUS_LABELS.get(r['status'], r['status'])
        
        # Mahsulotlarni olamiz
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += f"   • {item['item_name']}: {item['quantity_requested']} та (Етишмайди: {item['quantity_missing']})\n"
            
        text = (
            f"🆔 <b>Заявка №{r['id']}</b>\n"
            f"👤 Яратувчи: {r['creator_name']}\n"
            f"📋 Тавсиф: {r['description']}\n"
            f"⚙️ Ҳолати: {status_label}\n"
            f"🔍 Маҳсулотлар:\n{items_text}"
            f"📅 Сана: {r['created_at'][:16].replace('T', ' ')}"
        )
        
        # Boshqaruvchi va Super Admin uchun tasdiqlash tugmalari (agar status pending_approval bo'lsa)
        reply_markup = None
        if user['role'] in ['manager', 'super_admin'] and r['status'] == 'pending_approval':
            reply_markup = get_request_manage_keyboard(r['id'])
            
        await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")

@router.message(F.text.in_(["Заявкалар ҳаракати 🔄", "Zayavkalar harakati 🔄"]))
async def show_requests_movement(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager']:
        await message.answer("Сизда ушбу маълумотни кўриш ҳуқуқи йўқ.")
        return
        
    movements = await db.get_requests_movement()
    if not movements:
        await message.answer("Ҳозирча ҳеч қандай заявка мавжуд эмас.")
        return
        
    await message.answer("🔄 <b>Заявкалар ҳаракати ва йўналишлари:</b>", parse_mode="HTML")
    
    for r in movements:
        status_label = STATUS_LABELS.get(r['status'], r['status'])
        
        # Participants flow
        flow_text = f"👤 <b>Яратди (Механик):</b> {r['creator_name'] or '—'}\n"
        
        if r['approved_by']:
            flow_text += f"📥 <b>Тасдиқлади (Бошқарувчи):</b> {r['approver_name'] or '—'}\n"
        else:
            flow_text += f"📥 <b>Тасдиқлади:</b> кутилмоқда ⏳\n"
            
        if r['warehouse_released_by']:
            flow_text += f"📦 <b>Тайёрлади (Склад):</b> {r['warehouseman_name'] or '—'}\n"
            
        if r['courier_id']:
            flow_text += f"🚚 <b>Етказувчи (Таъминотчи):</b> {r['courier_name'] or '—'}\n"
            
        if r['status'] == 'completed':
            flow_text += f"✅ <b>Ўрнатилди ва якунланди (Механик):</b> {r['creator_name'] or '—'}\n"
        elif r['status'] == 'rejected':
            flow_text += f"❌ <b>Рад этилди</b>\n"

        text = (
            f"🆔 <b>Заявка №{r['id']}</b>\n"
            f"🚗 Машина: <b>{r['vehicle_name']}</b>\n"
            f"⚙️ Ҳолати: <b>{status_label}</b>\n\n"
            f"📈 <b>Жараён занжири (Йўналиш):</b>\n{flow_text}\n"
            f"📅 Сана: {r['created_at'][:16].replace('T', ' ')}\n"
            f"-------------------"
        )
        await message.answer(text, parse_mode="HTML")

