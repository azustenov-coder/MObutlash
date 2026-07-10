from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import database as db
from handlers.common import get_main_keyboard
from handlers.controller import STATUS_LABELS

router = Router()

class RequestCreationStates(StatesGroup):
    waiting_for_general_desc = State()
    waiting_for_item_name = State()
    waiting_for_item_qty = State()

@router.message(F.text == "Yangi zayavka yaratish ✍️")
async def start_request_creation(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['mechanic', 'brigadier']:
        await message.answer("Sizda zayavka yaratish huquqi yo'q.")
        return
        
    await message.answer(
        "📝 Yangi zayavka yaratish boshlandi.\n"
        "Zayavka uchun umumiy tavsif/nom kiriting:\n"
        "(Masalan: 'T-150 traktori butlash' yoki 'Sklad 2 uchun')",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RequestCreationStates.waiting_for_general_desc)

@router.message(RequestCreationStates.waiting_for_general_desc)
async def process_general_desc(message: Message, state: FSMContext):
    await state.update_data(general_desc=message.text, items=[])
    
    # Ombordagi mavjud mahsulotlarni ko'rsatamiz tugma qilib
    stock = await db.get_all_inventory()
    keyboard_buttons = []
    
    row = []
    for item in stock:
        row.append(KeyboardButton(text=item['name']))
        if len(row) == 2:
            keyboard_buttons.append(row)
            row = []
    if row:
        keyboard_buttons.append(row)
        
    # Tugallash tugmasi
    keyboard_buttons.append([KeyboardButton(text="Tugallash / Zayavkani yuborish 📨")])
    
    markup = ReplyKeyboardMarkup(keyboard=keyboard_buttons, resize_keyboard=True)
    
    await message.answer(
        "Rahmat. Endi zayavkaga kiruvchi mahsulot nomini yuboring:\n"
        "Quyidagi tugmalardan tanlashingiz yoki yangi nom yozishingiz mumkin.\n"
        "Barcha mahsulotlarni qo'shib bo'lgach 'Tugallash' tugmasini bosing.",
        reply_markup=markup
    )
    await state.set_state(RequestCreationStates.waiting_for_item_name)

@router.message(RequestCreationStates.waiting_for_item_name)
async def process_item_name(message: Message, state: FSMContext):
    text = message.text.strip()
    
    if text == "Tugallash / Zayavkani yuborish 📨":
        data = await state.get_data()
        items = data.get('items', [])
        
        if not items:
            await message.answer("Siz hech qanday mahsulot kiritmadingiz. Iltimos mahsulot kiriting yoki /start yuboring.")
            return
            
        # Zayavkani bazada yaratamiz
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        
        # Requests jadvaliga yozish
        request_id = await db.create_request(created_by=user_id, description=data['general_desc'])
        
        # Har bir mahsulotni solishtirib yozamiz
        summary_text = (
            f"📝 **Zayavka №{request_id} muvaffaqiyatli yaratildi!**\n"
            f"📋 **Tavsif:** {data['general_desc']}\n"
            f"👤 **Yuboruvchi:** {user['full_name']}\n\n"
            f"🔍 **Mahsulotlar solishtiruvi (Ombor bilan):**\n"
        )
        
        for item in items:
            name = item['name']
            requested = item['requested']
            
            # Sklad zaxirasi bilan tekshiramiz
            inv_item = await db.get_inventory_item(name)
            available = inv_item['quantity'] if inv_item else 0
            missing = max(0, requested - available)
            
            # Request_items jadvaliga yozish
            await db.add_request_item(
                request_id=request_id,
                item_name=name,
                quantity_requested=requested,
                quantity_available=available,
                quantity_missing=missing
            )
            
            summary_text += (
                f"🔹 **{name}**\n"
                f"   • So'ralgan: {requested} dona\n"
                f"   • Omborda bor: {available} dona\n"
                f"   • Yetishmaydi (Olib kelinadi): {missing} dona\n"
            )
            
        await state.clear()
        
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
        return
        
    # Aks holda, mahsulot nomini saqlab, sonini so'raymiz
    await state.update_data(current_item_name=text)
    await message.answer(
        f"🔢 '{text}' dan nechta kerak? Sonini kiriting:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RequestCreationStates.waiting_for_item_qty)

@router.message(RequestCreationStates.waiting_for_item_qty)
async def process_item_qty(message: Message, state: FSMContext):
    try:
        qty = int(message.text)
        if qty <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("Iltimos, musbat butun son kiriting:")
        return
        
    data = await state.get_data()
    items = data.get('items', [])
    
    # Yangi mahsulotni ro'yxatga qo'shamiz
    items.append({
        'name': data['current_item_name'],
        'requested': qty
    })
    
    await state.update_data(items=items)
    
    # Qayta klaviaturani ko'rsatish
    stock = await db.get_all_inventory()
    keyboard_buttons = []
    
    row = []
    for item in stock:
        row.append(KeyboardButton(text=item['name']))
        if len(row) == 2:
            keyboard_buttons.append(row)
            row = []
    if row:
        keyboard_buttons.append(row)
        
    keyboard_buttons.append([KeyboardButton(text="Tugallash / Zayavkani yuborish 📨")])
    markup = ReplyKeyboardMarkup(keyboard=keyboard_buttons, resize_keyboard=True)
    
    await message.answer(
        f"✅ {data['current_item_name']} - {qty} dona qo'shildi.\n\n"
        f"Yana mahsulot qo'shasizmi? Nomini yozing yoki tanlang, yoki 'Tugallash' tugmasini bosing:",
        reply_markup=markup
    )
    await state.set_state(RequestCreationStates.waiting_for_item_name)

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
