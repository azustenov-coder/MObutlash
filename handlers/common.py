from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import re
import database as db

router = Router()

class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_role = State()

ROLE_LABELS = {
    'manager': 'Boshqaruvchi 💼',
    'observer': 'Kuzatuvchi 👁️',
    'mechanic': 'Mexanik 🔧',
    'brigadier': 'Brigadir BR 🚜',
    'courier': 'Yetkazib beruvchi 🚚',
    'warehouseman': 'Skladchik 📦'
}

ROLE_REVERSE = {v: k for k, v in ROLE_LABELS.items()}

def get_role_by_input(text: str) -> str:
    if not text:
        return None
    cleaned = text.lower().strip()
    cleaned = re.sub(r'[^\w\s]', '', cleaned)
    cleaned = cleaned.strip()
    
    matches = {
        'boshqaruvchi': 'manager',
        'manager': 'manager',
        'kuzatuvchi': 'observer',
        'observer': 'observer',
        'mexanik': 'mechanic',
        'mechanic': 'mechanic',
        'brigadir': 'brigadier',
        'brigadir br': 'brigadier',
        'brigadier': 'brigadier',
        'yetkazib beruvchi': 'courier',
        'kuryer': 'courier',
        'courier': 'courier',
        'skladchik': 'warehouseman',
        'omborchi': 'warehouseman',
        'warehouseman': 'warehouseman'
    }
    return matches.get(cleaned)

def get_role_keyboard():
    keyboard = []
    # Qatoriga 2 tadan tugma joylashtiramiz
    row = []
    for label in ROLE_LABELS.values():
        row.append(KeyboardButton(text=label))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_main_keyboard(role: str):
    keyboard = []
    if role == 'super_admin':
        keyboard = [
            [KeyboardButton(text="Tasdiqlash kutilayotganlar 👥"), KeyboardButton(text="Foydalanuvchilar ro'yxati 📋")],
            [KeyboardButton(text="Barcha zayavkalar 📝")],
            [KeyboardButton(text="Excel hisobot yuklab olish 📊"), KeyboardButton(text="Ombor qoldiqlari 📦")]
        ]
    elif role == 'manager':
        keyboard = [
            [KeyboardButton(text="Tasdiqlash kutilayotgan zayavkalar 📥")],
            [KeyboardButton(text="Barcha zayavkalar 📝"), KeyboardButton(text="Foydalanuvchilar ro'yxati 📋")],
            [KeyboardButton(text="Excel hisobot yuklab olish 📊"), KeyboardButton(text="Ombor qoldiqlari 📦")]
        ]
    elif role == 'observer':
        keyboard = [
            [KeyboardButton(text="Barcha zayavkalar 📝"), KeyboardButton(text="Foydalanuvchilar ro'yxati 📋")]
        ]
    elif role in ['mechanic', 'brigadier']:
        keyboard = [
            [KeyboardButton(text="Yangi zayavka yaratish ✍️")],
            [KeyboardButton(text="Mening zayavkalarim 📂")]
        ]
    elif role == 'warehouseman':
        keyboard = [
            [KeyboardButton(text="Tayyorlanishi kutilayotganlar 📦"), KeyboardButton(text="Ombor zaxirasini boshqarish ⚙️")],
            [KeyboardButton(text="Barcha zayavkalar 📝"), KeyboardButton(text="Ombor qoldiqlari 📦")],
            [KeyboardButton(text="Excel hisobot yuklab olish 📊")]
        ]
    elif role == 'courier':
        keyboard = [
            [KeyboardButton(text="Yetkazilishi kutilayotganlar 🚚")],
            [KeyboardButton(text="Aktiv yetkazuvlarim 🛣️")]
        ]
    
    if not keyboard:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    from config import ADMIN_ID
    telegram_id = message.from_user.id

    # Agar foydalanuvchi Super Admin bo'lsa, ro'yxatdan o'tkazmasdan to'g'ridan-to'g'ri kiritamiz
    if ADMIN_ID and telegram_id == ADMIN_ID:
        await db.add_user(
            telegram_id=telegram_id,
            full_name=message.from_user.full_name or "Super Admin",
            phone="ADMIN",
            role="super_admin"
        )
        user = await db.get_user(telegram_id)
    else:
        user = await db.get_user(telegram_id)

    if not user:
        await message.answer(
            "Assalomu alaykum! 'MO Butlash' botiga xush kelibsiz.\n"
            "Botdan foydalanish uchun ro'yxatdan o'tishingiz kerak.\n\n"
            "Iltimos, to'liq ism-sharifingizni kiriting (F.I.Sh):",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(RegistrationStates.waiting_for_name)
    elif user['is_approved'] == 1:
        role_text = ROLE_LABELS.get(user['role'], user['role'])
        if user['role'] == 'super_admin':
            role_text = "Super Admin 👑"
        await message.answer(
            f"👋 Xush kelibsiz, {user['full_name']}!\n"
            f"🔑 Sizning rolingiz: {role_text}",
            reply_markup=get_main_keyboard(user['role'])
        )
    else:
        await message.answer(
            "⏳ Sizning so'rovingiz hali ko'rib chiqilmoqda. Admin tasdiqlashini kuting.",
            reply_markup=ReplyKeyboardRemove()
        )

# /menu komandasi - /start'ni bosmasdan menyuni chaqirish
@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. /start bosing.")
        return
    if user['is_approved'] != 1:
        await message.answer("Siz hali tasdiqlanmagansiz. Admin tasdiqlashini kuting.")
        return
    role_text = ROLE_LABELS.get(user['role'], user['role'])
    if user['role'] == 'super_admin':
        role_text = "Super Admin 👑"
    await message.answer(
        f"🔄 Menyu yangilandi!\n🔑 Rolingiz: {role_text}",
        reply_markup=get_main_keyboard(user['role'])
    )



@router.message(RegistrationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    
    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Telefon raqamni yuborish 📞", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "Rahmat. Endi telefon raqamingizni yuboring (yoki tugmani bosing):",
        reply_markup=phone_keyboard
    )
    await state.set_state(RegistrationStates.waiting_for_phone)

@router.message(RegistrationStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = ""
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text
        
    await state.update_data(phone=phone)
    
    await message.answer(
        "Iltimos, botdagi rolingizni tanlang:",
        reply_markup=get_role_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_role)

@router.message(RegistrationStates.waiting_for_role)
async def process_role(message: Message, state: FSMContext):
    selected_role_label = message.text
    role_key = get_role_by_input(selected_role_label)
    
    if not role_key:
        await message.answer(
            "Iltimos, quyidagi tugmalardan birini tanlang:",
            reply_markup=get_role_keyboard()
        )
        return
        
    user_data = await state.get_data()
    telegram_id = message.from_user.id
    
    final_role, is_approved = await db.add_user(
        telegram_id=telegram_id,
        full_name=user_data['full_name'],
        phone=user_data['phone'],
        role=role_key
    )
    
    await state.clear()
    
    if final_role == 'super_admin':
        await message.answer(
            "Siz birinchi foydalanuvchi bo'lganingiz uchun avtomatik ravishda Super Admin roliga tayinlandingiz va tasdiqlandingiz! 👑",
            reply_markup=get_main_keyboard(final_role)
        )
    else:
        await message.answer(
            "Rahmat! Ro'yxatdan o'tish so'rovingiz qabul qilindi. Admin uni tasdiqlaganidan so'ng sizga xabar yuboriladi.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Super adminlarni ogohlantirish
        super_admins = await db.get_users_by_role('super_admin')
        for admin in super_admins:
            try:
                from main import bot
                await bot.send_message(
                    admin['telegram_id'],
                    f"🔔 Yangi ro'yxatdan o'tish so'rovi:\n\n"
                    f"👤 F.I.Sh: {user_data['full_name']}\n"
                    f"📞 Telefon: {user_data['phone']}\n"
                    f"💼 Tanlangan rol: {selected_role_label}\n\n"
                    f"Tasdiqlash uchun Super Admin menyusidan foydalaning."
                )
            except Exception as e:
                print(f"Adminni ogohlantirishda xato: {e}")

# Excel hisobot yuklab olish
@router.message(F.text == "Excel hisobot yuklab olish 📊")
async def download_excel_report(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager', 'warehouseman']:
        await message.answer("Sizda hisobot yuklab olish huquqi yo'q.")
        return
        
    await message.answer("Hisobot tayyorlanmoqda, iltimos kuting... ⏳")
    try:
        from aiogram.types import FSInputFile
        file_path = await db.export_requests_to_excel()
        await message.answer_document(
            document=FSInputFile(file_path),
            caption="📝 Barcha zayavkalar va ombor qoldiqlari hisoboti"
        )
    except Exception as e:
        await message.answer(f"Hisobot yaratishda xatolik yuz berdi: {e}")

# Ombor qoldiqlari ro'yxatini ko'rish
@router.message(F.text == "Ombor qoldiqlari 📦")
async def show_warehouse_stock(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager', 'warehouseman']:
        await message.answer("Sizda ushbu ma'lumotni ko'rish huquqi yo'q.")
        return
        
    stock = await db.get_all_inventory()
    if not stock:
        await message.answer("Ombor bo'sh. Hozircha hech qanday mahsulot mavjud emas.")
        return
        
    text = "📦 **Ombordagi bor mahsulotlar (Qoldiqlar):**\n\n"
    for item in stock:
        text += f"🔹 **{item['name']}** — {item['quantity']} dona\n"
        
    await message.answer(text, parse_mode="Markdown")

