from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove
import database as db
from handlers.common import get_main_keyboard
from handlers.controller import STATUS_LABELS

router = Router()

class RequestCreationStates(StatesGroup):
    waiting_for_desc = State()

@router.message(F.text == "Yangi zayavka yaratish ✍️")
async def start_request_creation(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Sizda zayavka yaratish huquqi yo'q.")
        return
        
    await message.answer(
        "📝 **Yangi zayavka yaratish:**\n"
        "Zayavka tarkibini to'liq yozib yuboring (Masalan: '10 ta balon, gidravlik shlanka 2 ta'):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RequestCreationStates.waiting_for_desc)

@router.message(RequestCreationStates.waiting_for_desc)
async def process_request_desc(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    description = message.text.strip()
    
    # Zayavkani bazada yaratamiz
    request_id = await db.create_request(created_by=user_id, description=description)
    
    # Bitta request_item yaratamiz (tavsif bilan bir xil, miqdori 1 ta)
    await db.add_request_item(
        request_id=request_id,
        item_name=description,
        quantity_requested=1,
        quantity_available=0,
        quantity_missing=1
    )
    
    await state.clear()
    
    summary_text = (
        f"📝 **Zayavka №{request_id} muvaffaqiyatli yaratildi va tasdiqlashga yuborildi!**\n\n"
        f"📋 **Zayavka tarkibi:** {description}\n"
        f"👤 **Yuboruvchi:** {user['full_name']}"
    )
    
    # Mexanikka javob
    await message.answer(summary_text, reply_markup=get_main_keyboard(user['role']), parse_mode="Markdown")
    
    # Boshqaruvchilarni ogohlantirish
    managers = await db.get_users_by_role('manager')
    for m in managers:
        try:
            from main import bot
            await bot.send_message(
                m['telegram_id'],
                f"🔔 **Yangi zayavka tasdiqlash uchun keldi! (№{request_id})**\n\n" + summary_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Boshqaruvchini ogohlantirishda xato: {e}")
            
    # Super adminlarni ogohlantirish
    super_admins = await db.get_users_by_role('super_admin')
    for sa in super_admins:
        try:
            from main import bot
            await bot.send_message(
                sa['telegram_id'],
                f"🔔 **Yangi zayavka tasdiqlash uchun keldi! (№{request_id})**\n\n" + summary_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Super adminni ogohlantirishda xato: {e}")

@router.message(F.text == "Mening zayavkalarim 📂")
async def show_my_requests(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Sizda zayavkalarni ko'rish huquqi yo'q.")
        return
        
    my_reqs = await db.get_my_requests(message.from_user.id)
    if not my_reqs:
        await message.answer("Siz hali birorta ham zayavka yaratmagansiz.")
        return
        
    text = "📂 **Sizning zayavkalaringiz ro'yxati:**\n\n"
    for r in my_reqs[:15]:  # Oxirgi 15 tasini ko'rsatamiz
        status_label = STATUS_LABELS.get(r['status'], r['status'])
        text += (
            f"🆔 **Zayavka №{r['id']}**\n"
            f"📋 Tavsif: {r['description']}\n"
            f"⚙️ Holati: {status_label}\n"
            f"📅 Sana: {r['created_at'][:16].replace('T', ' ')}\n"
            f"-------------------\n"
        )
    await message.answer(text, parse_mode="Markdown")
