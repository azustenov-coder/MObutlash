from aiogram import Router, F
from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database as db
from handlers.common import get_request_manage_keyboard

router = Router()


class LeadershipRoleFilter(Filter):
    """Let this shared menu be handled only for the three leadership roles."""
    async def __call__(self, message: Message) -> bool:
        user = await db.get_user(message.from_user.id)
        return bool(user and user['role'] in ['super_admin', 'manager', 'observer'])

# Tasdiqlashdan keyingi ta'minot jarayoni holatlari.
APPROVED_PIPELINE_STATUSES = {
    'approved', 'delivering', 'searching', 'purchased',
    'waiting_receipt', 'ready_for_installation', 'issued_to_mechanic', 'completed',
}

STATUS_LABELS = {
    'pending_approval': 'Тасдиқлаш кутилмоқда ⏳',
    'pending_admin_approval': 'Бошқарувчи тасдиқлаган (Админ кутилмоқда) ⏳',
    'approved': 'Тасдиқланган (Таъминотчи кутилмоқда) 🚚',
    'delivering': 'Йўлда 🛣️',
    'searching': 'Қидирилмоқда 🔍',
    'purchased': 'Сотиб олинди (Йўлда) 🛒',
    'waiting_receipt': 'Қабул кутилмоқда 📥',
    'ready_for_installation': 'Омборга келган (Ўрнатилиши кутилмоқда) 🛠️',
    'issued_to_mechanic': 'Складдан олинди, ўрнатиш кутилмоқда 📦',
    'completed': 'Ўрнатилди ва якунланди ✅',
    'rejected': 'Рад этилди ❌'
}


def get_approval_target_status(request_type: str | None) -> str:
    """Route repairs straight to the creator; purchases use the supply chain."""
    return 'issued_to_mechanic' if request_type == 'repair' else 'approved'


async def send_installation_photo(message: Message, request: dict):
    """Show the mechanic's proof photo directly under a completed request."""
    photo_id = request.get('installed_part_photo')
    if request.get('status') != 'completed' or not photo_id:
        return
    try:
        await message.answer_photo(
            photo=photo_id,
            caption=f"📸 Заявка №{request['id']} — ўрнатилган ҳолат расми",
        )
    except Exception as exc:
        print(f"O'rnatish rasmini ko'rsatishda xato: {exc}")


@router.message(
    F.text.in_(["Tugallanmagan zayavkalar ⏳", "Тугалланмаган заявкалар ⏳"])
    | F.text.startswith("Tugallanmagan zayavkalar ⏳")
    | F.text.startswith("Тугалланмаган заявкалар ⏳"),
    LeadershipRoleFilter(),
)
async def show_open_requests_for_leadership(message: Message):
    requests = await db.get_open_requests()
    if not requests:
        await message.answer("✅ Ҳозирда тугалланмаган заявка мавжуд эмас.")
        return

    chunks = []
    current = "⏳ <b>Барча тугалланмаган заявкалар:</b>\n\n"
    for request in requests:
        status_label = STATUS_LABELS.get(request['status'], request['status'])
        request_block = (
            f"🆔 <b>Заявка №{request['id']}</b>\n"
            f"👤 Яратувчи: {request['creator_name'] or '—'}\n"
            f"🚗 Машина: {request['vehicle_name'] or '—'}\n"
            f"📋 Тавсиф: {request['description']}\n"
            f"⚙️ Ҳолати: <b>{status_label}</b>\n"
            f"🕒 Янгиланган: {db.format_datetime(request['updated_at'])}\n"
            f"-------------------\n"
        )
        if len(current) + len(request_block) > 3800 and current.strip():
            chunks.append(current)
            current = request_block
        else:
            current += request_block
    if current.strip():
        chunks.append(current)

    for chunk in chunks:
        await message.answer(chunk, parse_mode="HTML")


@router.message(
    F.text.in_(["Tugallangan zayavkalar ✅", "Тугалланган заявкалар ✅"])
    | F.text.startswith("Tugallangan zayavkalar ✅")
    | F.text.startswith("Тугалланган заявкалар ✅"),
    LeadershipRoleFilter(),
)
async def show_completed_requests_for_leadership(message: Message):
    requests = await db.get_completed_requests()
    if not requests:
        await message.answer("Ҳозирча якунланган заявка мавжуд эмас.")
        return

    await message.answer("✅ <b>Барча тугалланган заявкалар:</b>", parse_mode="HTML")
    for request in requests:
        await message.answer(
            f"🆔 <b>Заявка №{request['id']}</b>\n"
            f"👤 Яратувчи: {request['creator_name'] or '—'}\n"
            f"🚗 Машина: {request['vehicle_name'] or '—'}\n"
            f"📋 Тавсиф: {request['description']}\n"
            f"🕒 Якунланган: {db.format_datetime(request['updated_at'])}",
            parse_mode="HTML",
        )
        await send_installation_photo(message, request)

@router.message(F.text.in_(["Kutilayotgan zayavkalar 📥", "Кутилаётган заявкалар 📥"]) | F.text.startswith("Kutilayotgan zayavkalar 📥") | F.text.startswith("Кутилаётган заявкалар 📥"))
async def list_pending_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['manager', 'super_admin', 'observer']:
        await message.answer("Сизда ушбу командани бажариш учун ҳуқуқ йўқ.")
        return
        
    pending = await db.get_requests_by_status('pending_approval')
    pending.extend(await db.get_requests_by_status('pending_admin_approval'))
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
            
        created_at = r['created_at']
        if hasattr(created_at, 'strftime'):
            date_str = created_at.strftime('%Y-%m-%d %H:%M')
        else:
            date_str = str(created_at)[:16].replace('T', ' ')
            
        text = (
            f"📝 <b>Заявка №{r['id']}</b>\n"
            f"👤 <b>Яратувчи:</b> {r['creator_name']} (ID: {r['created_by']})\n"
            f"📋 <b>Тавсиф:</b> {r['description']}\n\n"
            f"🔍 <b>Маҳсулотлар таркиби:</b>\n{items_text}\n"
            f"📅 <b>Яратилган вақт:</b> {date_str}"
        )
        await message.answer(
            text, 
            reply_markup=get_request_manage_keyboard(r['id']),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("bulk_approve_"))
async def bulk_approve_request(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['manager', 'super_admin', 'observer']:
        await callback.answer("Сизда заявкаларни тасдиқлаш ҳуқуқи йўқ!", show_alert=True)
        return
        
    batch_id = int(callback.data.split("_")[2])
    requests = await db.get_requests_by_batch(batch_id)
    if not requests:
        await callback.answer("Заявкалар топилмади.")
        await callback.message.delete()
        return
        
    pending_reqs = [r for r in requests if r['status'] in ['pending_approval', 'pending_admin_approval']]
    if not pending_reqs:
        await callback.answer("Ушбу пакетдаги барча заявкалар аллақачон кўриб чиқилган!", show_alert=True)
        await callback.message.delete()
        return
        
    approved_count = 0
    role_label = user['role']
    for req in pending_reqs:
        target_status = get_approval_target_status(req.get('request_type'))
        await db.update_request_status(req['id'], target_status, callback.from_user.id, role_label)
        approved_count += 1
        
    await callback.answer(f"Пакетдаги {approved_count} та заявка муваффақиятли тасдиқланди.")
    
    role_display = {
        'super_admin': "Супер Админ 👑",
        'manager': "Бошқарувчи 💼",
        'observer': "Бошқарувчи 2 💼",
    }[user['role']]
    
    summary = (
        f"✅ <b>Пакет №{batch_id} даги барча заявкалар ({approved_count} та) {role_display} томонидан тасдиқланди!</b>\n"
        f"👤 <b>Тасдиқлади:</b> {user['full_name']}\n"
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=None, parse_mode="HTML")
    else:
        await callback.message.edit_text(text=summary, reply_markup=None, parse_mode="HTML")

@router.callback_query(F.data.startswith("bulk_reject_"))
async def bulk_reject_request(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['manager', 'super_admin', 'observer']:
        await callback.answer("Сизда рад etish huquqi yo'q!", show_alert=True)
        return
        
    batch_id = int(callback.data.split("_")[2])
    requests = await db.get_requests_by_batch(batch_id)
    if not requests:
        await callback.answer("Заявкалар топилмади.")
        await callback.message.delete()
        return
        
    pending_reqs = [r for r in requests if r['status'] in ['pending_approval', 'pending_admin_approval']]
    if not pending_reqs:
        await callback.answer("Ушбу пакетдаги барча заявкалар аллақачон кўриб чиқилган!", show_alert=True)
        await callback.message.delete()
        return
        
    role_label = user['role']
    for req in pending_reqs:
        await db.update_request_status(req['id'], 'rejected', callback.from_user.id, role_label)
        
    await callback.answer("Пакетдаги барча заявкалар рад etildi.")
    
    role_display = {
        'super_admin': "Супер Админ 👑",
        'manager': "Бошқарувчи 💼",
        'observer': "Бошқарувчи 2 💼",
    }[user['role']]
    
    summary = (
        f"❌ <b>Пакет №{batch_id} даги барча заявкалар {role_display} томонидан рад etildi!</b>\n"
        f"👤 <b>Рад этди:</b> {user['full_name']}\n"
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=None, parse_mode="HTML")
    else:
        await callback.message.edit_text(text=summary, reply_markup=None, parse_mode="HTML")

@router.callback_query(F.data.startswith("bulk_revision_"))
async def bulk_revision_request(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['manager', 'super_admin', 'observer']:
        await callback.answer("Сизда қайта ишлашга юбориш ҳуқуқи йўқ!", show_alert=True)
        return
        
    batch_id = int(callback.data.split("_")[2])
    requests = await db.get_requests_by_batch(batch_id)
    if not requests:
        await callback.answer("Заявкалар топилмади.")
        await callback.message.delete()
        return
        
    pending_reqs = [r for r in requests if r['status'] in ['pending_approval', 'pending_admin_approval']]
    if not pending_reqs:
        await callback.answer("Ушбу пакетдаги барча заявкалар аллақачон кўриб чиқилган!", show_alert=True)
        await callback.message.delete()
        return
        
    role_label = user['role']
    for req in pending_reqs:
        await db.update_request_status(req['id'], 'revision', callback.from_user.id, role_label)
        
    await callback.answer("Пакетдаги барча заявкалар қайта ишлашга юборилди.")
    
    role_display = {
        'super_admin': "Супер Админ 👑",
        'manager': "Бошқарувчи 💼",
        'observer': "Бошқарувчи 2 💼",
    }[user['role']]
    
    summary = (
        f"🔄 <b>Пакет №{batch_id} даги барча заявкалар {role_display} томонидан қайта ишлашга юборилди!</b>\n"
        f"👤 <b>Юборди:</b> {user['full_name']}\n"
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=summary, reply_markup=None, parse_mode="HTML")
    else:
        await callback.message.edit_text(text=summary, reply_markup=None, parse_mode="HTML")

@router.callback_query(F.data.startswith("req_approve_"))
async def approve_request(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['manager', 'super_admin', 'observer']:
        await callback.answer("Сизда заявкани тасдиқлаш ҳуқуқи йўқ!", show_alert=True)
        return
        
    request_id = int(callback.data.split("_")[2])
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("Заявка топилмади.")
        await callback.message.delete()
        return
        
    if req['status'] not in ['pending_approval', 'pending_admin_approval']:
        await callback.answer("Ушбу заявка аллақачон кўриб чиқилган!", show_alert=True)
        await callback.message.delete()
        return
        
    is_repair = req.get('request_type') == 'repair'
    target_status = get_approval_target_status(req.get('request_type'))
    role_label = user['role']
    await db.update_request_status(request_id, target_status, callback.from_user.id, role_label)
    if is_repair:
        await callback.answer("Таъмирлаш заявкаси тасдиқланди ва механикка бажариш учун юборилди.")
    else:
        await callback.answer("Заявка тасдиқланди ва таъминотчиларга юборилди.")
    
    # Zayavka tarkibi
    items = await db.get_request_items(request_id)
    items_text = ""
    for item in items:
        items_text += (
            f"   • <b>{item['item_name']}</b> — Сўралган: {item['quantity_requested']} дона | "
            f"Омборда: {item['quantity_available']} | "
            f"Етишмайди (Олинади): {item['quantity_missing']}\n"
        )
        
    created_at = req['created_at']
    if hasattr(created_at, 'strftime'):
        created_date = created_at.strftime('%Y-%m-%d %H:%M')
    else:
        created_date = str(created_at)[:16].replace('T', ' ')
    role_display = {
        'super_admin': "Супер Админ 👑",
        'manager': "Бошқарувчи 💼",
        'observer': "Бошқарувчи 2 💼",
    }[user['role']]
    destination_text = "механикка бажариш учун юборилди" if is_repair else "етказишга юборилди"
    summary = (
        f"✅ <b>Заявка №{request_id} {role_display} томонидан тасдиқланди ва {destination_text}.</b>\n"
        f"📋 Тавсиф: {req['description']}\n"
        f"📅 <b>Сана:</b> {created_date}\n"
        f"👤 Тасдиқлади: {user['full_name']}\n\n"
        f"🔍 <b>Маҳсулотлар таркиби:</b>\n{items_text}"
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=summary,
            reply_markup=None,
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            summary,
            reply_markup=None,
            parse_mode="HTML"
        )
    
    if not is_repair:
        # Only purchase requests need the supplier -> warehouse pipeline.
        from handlers.common import get_courier_take_keyboard
        couriers = await db.get_users_by_role('courier')
        for c in couriers:
            try:
                from main import bot
                msg_text = (
                    f"🚚 <b>Янги буюртма (Заявка №{request_id}) етказиш учун келди!</b>\n\n"
                    f"Механик/Бригадир: {req['creator_name']}\n"
                    f"📋 Тавсиф: {req['description']}\n"
                    f"📅 <b>Сана:</b> {created_date}\n\n"
                    f"🔍 <b>Олиб келинадиган товарлар (Етишмаётган қолдиқ):</b>\n{items_text}\n"
                    f"Етказишни қабул қилиш учун пастдаги тугмани босинг."
                )
                kb = get_courier_take_keyboard(request_id)
                if req['old_part_photo']:
                    await bot.send_photo(
                        c['telegram_id'],
                        photo=req['old_part_photo'],
                        caption=msg_text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                else:
                    await bot.send_message(
                        c['telegram_id'],
                        text=msg_text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
            except Exception as e:
                print(f"Ta'minotchini ogohlantirishda xato: {e}")

    # Tasdiqlash natijasini boshqa boshqaruvchilarga real vaqt rejimida yuborish.
    # Ular keyingi menyu so'rovida ham aynan shu holatni PostgreSQL dan ko'radi.
    reviewers = list(await db.get_users_by_role('manager'))
    reviewers.extend(await db.get_users_by_role('super_admin'))
    reviewers.extend(await db.get_users_by_role('observer'))
    for reviewer in reviewers:
        if reviewer['telegram_id'] == callback.from_user.id:
            continue
        try:
            from main import bot
            await bot.send_message(
                reviewer['telegram_id'],
                f"✅ <b>Zayavka №{request_id} tasdiqlandi.</b>\n"
                f"👤 Tasdiqladi: {user['full_name']} ({role_display})\n"
                f"📋 Tavsif: {req['description']}\n"
                f"📅 Sana: {created_date}",
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Boshqaruvchini tasdiqlash haqida ogohlantirishda xato: {e}")
            
    # Yaratuvchini (Mexanik/Brigadir) ogohlantirish
    try:
        from main import bot
        if is_repair:
            from handlers.common import get_mechanic_install_keyboard
            await bot.send_message(
                req['created_by'],
                f"✅ Сизнинг №{request_id}-сонли таъмирлаш заявкангиз тасдиқланди. "
                f"Ишни бажариб, исбот расмини юборинг.",
                reply_markup=get_mechanic_install_keyboard(request_id),
            )
        else:
            await bot.send_message(
                req['created_by'],
                f"✅ Сизнинг №{request_id}-сонли заявкангиз тасдиқланди ва таъминотчиларга юборилди."
            )
    except Exception as e:
        print(f"Yaratuvchini ogohlantirishda xato: {e}")

@router.callback_query(F.data.startswith("req_reject_"))
async def reject_request(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user['role'] not in ['manager', 'super_admin', 'observer']:
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
    
    created_at = req['created_at']
    if hasattr(created_at, 'strftime'):
        created_date = created_at.strftime('%Y-%m-%d %H:%M')
    else:
        created_date = str(created_at)[:16].replace('T', ' ')
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
    if not user or user['role'] not in ['manager', 'super_admin', 'observer']:
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
    
    created_at = req['created_at']
    if hasattr(created_at, 'strftime'):
        created_date = created_at.strftime('%Y-%m-%d %H:%M')
    else:
        created_date = str(created_at)[:16].replace('T', ' ')
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

@router.message(F.text.in_(["Barcha zayavkalar 📝", "Барча заявкалар 📝"]) | F.text.startswith("Barcha zayavkalar 📝") | F.text.startswith("Барча заявкалар 📝"))
async def show_all_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager', 'observer', 'warehouseman']:
        await message.answer("Сизда заявкаларни кўриш ҳуқуқи йўқ.")
        return
        
    requests = await db.get_all_requests()
    approved_requests = [
        r for r in requests if r['status'] in APPROVED_PIPELINE_STATUSES
    ]
    if not approved_requests:
        await message.answer("Тизимда тасдиқланган ва таъминот жараёнига юборилган заявкалар йўқ.")
        return
        
    await message.answer("📝 <b>Тасдиқланган ва таъминот жараёнидаги заявкалар:</b>", parse_mode="HTML")
    
    for r in approved_requests:
        status_label = STATUS_LABELS.get(r['status'], r['status'])
        
        # Mahsulotlarni olamiz
        items = await db.get_request_items(r['id'])
        items_text = ""
        for item in items:
            items_text += f"   • {item['item_name']}: {item['quantity_requested']} та (Етишмайди: {item['quantity_missing']})\n"
            
        created_at = r['created_at']
        if hasattr(created_at, 'strftime'):
            date_str = created_at.strftime('%Y-%m-%d %H:%M')
        else:
            date_str = str(created_at)[:16].replace('T', ' ')
            
        text = (
            f"🆔 <b>Заявка №{r['id']}</b>\n"
            f"👤 Яратувчи: {r['creator_name']}\n"
            f"📋 Тавсиф: {r['description']}\n"
            f"⚙️ Ҳолати: {status_label}\n"
            f"🔍 Маҳсулотлар:\n{items_text}"
            f"📅 Сана: {date_str}"
        )
        
        await message.answer(text, parse_mode="HTML")
        await send_installation_photo(message, r)

@router.message(F.text.in_(["Заявкалар ҳаракати 🔄", "Zayavkalar harakati 🔄"]) | F.text.startswith("Заявкалар ҳаракати 🔄") | F.text.startswith("Zayavkalar harakati 🔄"))
async def show_requests_movement(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager', 'observer']:
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

        created_at = r['created_at']
        if hasattr(created_at, 'strftime'):
            date_str = created_at.strftime('%Y-%m-%d %H:%M')
        else:
            date_str = str(created_at)[:16].replace('T', ' ')
            
        text = (
            f"🆔 <b>Заявка №{r['id']}</b>\n"
            f"🚗 Машина: <b>{r['vehicle_name']}</b>\n"
            f"⚙️ Ҳолати: <b>{status_label}</b>\n\n"
            f"📈 <b>Жараён занжири (Йўналиш):</b>\n{flow_text}\n"
            f"📅 Сана: {date_str}\n"
            f"-------------------"
        )
        await message.answer(text, parse_mode="HTML")
        await send_installation_photo(message, r)

