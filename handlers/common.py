from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
import re
import database as db

router = Router()

class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_role = State()

ROLE_LABELS = {
    'manager': 'Boshqaruvchi 💼',
    'observer': 'Boshqaruvchi 2 💼',
    'mechanic': 'Mexanik 🔧',
    'brigadier': 'Brigadir BR 🚜',
    'courier': "Ta'minotchi 🚚",
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
        'boshqaruvchi 2': 'observer',
        'boshqaruvchi2': 'observer',
        'kuzatuvchi': 'observer',
        'observer': 'observer',
        'mexanik': 'mechanic',
        'mechanic': 'mechanic',
        'brigadir': 'brigadier',
        'brigadir br': 'brigadier',
        'brigadier': 'brigadier',
        'yetkazib beruvchi': 'courier',
        'taminotchi': 'courier',
        'taminotchi 🚚': 'courier',
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
            [KeyboardButton(text="Аъзолик сўровлари 👥"), KeyboardButton(text="Ходимлар рўйхати 📋")],
            [KeyboardButton(text="Кутилаётган заявкалар 📥"), KeyboardButton(text="Барча заявкалар 📝")],
            [KeyboardButton(text="Заявкалар ҳаракати 🔄"), KeyboardButton(text="Омбор қолдиқлари 📦")],
            [KeyboardButton(text="Excel ҳисобот юклаб олиш 📊")]
        ]
    elif role == 'manager':
        keyboard = [
            [KeyboardButton(text="Кутилаётган заявкалар 📥")],
            [KeyboardButton(text="Барча заявкалар 📝"), KeyboardButton(text="Ходимлар рўйхати 📋")],
            [KeyboardButton(text="Заявкалар ҳаракати 🔄"), KeyboardButton(text="Омбор қолдиқлари 📦")],
            [KeyboardButton(text="Excel ҳисобот юклаб олиш 📊")]
        ]
    elif role == 'observer':
        keyboard = [
            [KeyboardButton(text="Барча заявкалар 📝"), KeyboardButton(text="Ходимлар рўйхати 📋")]
        ]
    elif role in ['mechanic', 'brigadier']:
        keyboard = [
            [KeyboardButton(text="Соз автолар 🟢"), KeyboardButton(text="Носоз автолар 🔴")],
            [KeyboardButton(text="Автолар 🚗"), KeyboardButton(text="Менинг заявкаларим 📂")]
        ]
    elif role == 'warehouseman':
        keyboard = [
            [KeyboardButton(text="Тайёрланиши кутилаётганлар 📦"), KeyboardButton(text="Омбор захирасини бошқариш ⚙️")],
            [KeyboardButton(text="Барча заявкалар 📝"), KeyboardButton(text="Омбор қолдиқлари 📦")],
            [KeyboardButton(text="Excel ҳисобот юклаб олиш 📊")]
        ]
    elif role == 'courier':
        keyboard = [
            [KeyboardButton(text="Етказилиши кутилаётганлар 🚚")],
            [KeyboardButton(text="Актив етказувларим 🛣️")]
        ]
    
    if not keyboard:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    from config import ADMIN_ID
    telegram_id = message.from_user.id

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
            "Ассалому алайкум! 'MO Butlash' ботига хуш келибсиз.\n"
            "Ботдан фойдаланиш учун рўйхатдан ўтишингиз керак.\n\n"
            "Илтимос, тўлиқ исм-шарифингизни киритинг (Ф.И.Ш):",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(RegistrationStates.waiting_for_name)
    elif user['is_approved'] == 1:
        role_text = ROLE_LABELS.get(user['role'], user['role'])
        if user['role'] == 'super_admin':
            role_text = "Super Admin 👑"
        await message.answer(
            f"👋 Хуш келибсиз, {user['full_name']}!\n"
            f"🔑 Сизнинг ролингиз: {role_text}",
            reply_markup=get_main_keyboard(user['role'])
        )
    else:
        await message.answer(
            "⏳ Sizning so'rovingiz hali ko'rib chiqilmoqda. Admin tasdiqlashini kuting.",
            reply_markup=ReplyKeyboardRemove()
        )

# /menu komandasi
@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сиз ҳали рўйхатдан ўтмагансиз. /start босинг.")
        return
    if user['is_approved'] != 1:
        await message.answer("Сиз ҳали тасдиқланмагансиз. Админ тасдиқлашини кутинг.")
        return
    role_text = ROLE_LABELS.get(user['role'], user['role'])
    if user['role'] == 'super_admin':
        role_text = "Super Admin 👑"
    await message.answer(
        f"🔄 Меню янгиланди!\n🔑 Ролингиз: {role_text}",
        reply_markup=get_main_keyboard(user['role'])
    )


@router.message(RegistrationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    
    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Телефон рақамни юбориш 📞", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "Раҳмат. Энди телефон рақамингизни юборинг (ёки тугмани босинг):",
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
        "Илтимос, ботдаги ролингизни танланг:",
        reply_markup=get_role_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_role)

@router.message(RegistrationStates.waiting_for_role)
async def process_role(message: Message, state: FSMContext):
    selected_role_label = message.text
    role_key = get_role_by_input(selected_role_label)
    
    if not role_key:
        await message.answer(
            "Илтимос, қуйидаги тугмалардан бирини танланг:",
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
            "Сиз биринчи фойдаланувчи бўлганингиз учун автоматик равишda Супер Админ ролига тайинландингиз ва тасдиқландингиз! 👑",
            reply_markup=get_main_keyboard(final_role)
        )
    else:
        await message.answer(
            "Раҳмат! Рўйхатдан ўтиш сўровингиз қабул қилинди. Админ уни тасдиқлаганидан сўнг сизга хабар юборилади.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Super adminlarni ogohlantirish
        super_admins = await db.get_users_by_role('super_admin')
        for admin in super_admins:
            try:
                from main import bot
                await bot.send_message(
                    admin['telegram_id'],
                    f"🔔 Янги рўйхатдан ўтиш сўрови:\n\n"
                    f"👤 Ф.И.Ш: {user_data['full_name']}\n"
                    f"📞 Телефон: {user_data['phone']}\n"
                    f"💼 Танланган рол: {selected_role_label}\n\n"
                    f"Тасдиқлаш учун Супер Админ менюсидан фойдаланинг."
                )
            except Exception as e:
                print(f"Adminni ogohlantirishda xato: {e}")

# Excel hisobot yuklab olish
@router.message(F.text.in_(["Excel hisobot yuklab olish 📊", "Excel ҳисобот юклаб олиш 📊"]))
async def download_excel_report(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager', 'warehouseman']:
        await message.answer("Сизда ҳисобот юклаб олиш ҳуқуқи йўқ.")
        return
        
    await message.answer("Ҳисобот тайёрланмоқда, илтимос кутинг... ⏳")
    try:
        from aiogram.types import FSInputFile
        file_path = await db.export_requests_to_excel()
        await message.answer_document(
            document=FSInputFile(file_path),
            caption="📝 Барча заявкалар ва омбор қолдиқлари ҳисоботи"
        )
    except Exception as e:
        await message.answer(f"Ҳисобот яратишда хатолик юз берди: {e}")

# Ombor qoldiqlari ro'yxatini ko'rish
@router.message(F.text.in_(["Ombor qoldiqlari 📦", "Омбор қолдиқлари 📦"]))
async def show_warehouse_stock(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager', 'warehouseman']:
        await message.answer("Сизда ушбу маълумотни кўриш ҳуқуқи йўқ.")
        return
        
    stock = await db.get_all_inventory()
    if not stock:
        await message.answer("Омбор бўш. Ҳозирча ҳеч қандай маҳсулот мавжуд эмас.")
        return
        
    tayyor_items = [i for i in stock if i.get('category') == 'tayyor']
    butlovchi_items = [i for i in stock if i.get('category') != 'tayyor']
    
    text = "📦 **ОМБОР ҚОЛДИҚЛАРИ:**\n\n"
    
    text += "📦 **1. Тайёр маҳсулотлар:**\n"
    if tayyor_items:
        for item in tayyor_items:
            text += f"   • **{item['name']}** — {item['quantity']} dona\n"
    else:
        text += "   *Мавжуд эмас*\n"
        
    text += "\n⚙️ **2. Бутловчи маҳсулотлар:**\n"
    if butlovchi_items:
        for item in butlovchi_items:
            text += f"   • **{item['name']}** — {item['quantity']} dona\n"
    else:
        text += "   *Мавжуд эмас*\n"
        
    await message.answer(text, parse_mode="Markdown")


# --- GLOBAL INLINE KEYBOARDS ---

# Skladchik qabul qilishi uchun tugma
def get_wh_receipt_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Юкларни қабул қилдим ва тасдиқлайман ✅", callback_data=f"wh_receipt_confirm_{request_id}")]
    ])

# Yetkazib beruvchi yukni olish tugmasi
def get_courier_take_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Қабул қилдим 🚚", callback_data=f"cour_take_{request_id}")]
    ])

# Yetkazib beruvchi topshirish tugmasi
def get_courier_handover_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Топширдим 📦", callback_data=f"cour_handover_{request_id}")]
    ])

# Yetkazib beruvchi harakatlar tugmalari (Qidiryapman, Sotib oldim, Topshirdim)
def get_courier_action_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔎 Қидиряпман", callback_data=f"cour_search_{request_id}"),
            InlineKeyboardButton(text="🛒 Сотиб олдим", callback_data=f"cour_buy_{request_id}")
        ],
        [
            InlineKeyboardButton(text="📦 Топширдим", callback_data=f"cour_handover_{request_id}")
        ]
    ])

# Boshqaruvchi va Admin zayavka boshqarish tugmalari
def get_request_manage_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Тасдиқлаш ✅", callback_data=f"req_approve_{request_id}"),
            InlineKeyboardButton(text="Рад этиш ❌", callback_data=f"req_reject_{request_id}")
        ],
        [
            InlineKeyboardButton(text="Қайта ишлашга 🔄", callback_data=f"req_revision_{request_id}")
        ]
    ])

# Mexanik o'rnatilgan zapchast rasmini yuklashi uchun tugma
def get_mechanic_install_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ўрнатилди (Расм юбориш) 📸", callback_data=f"mech_install_{request_id}")]
    ])

# Mexanik uchun zayavkani qayta ishlash/tahrirlash tugmasi
def get_mechanic_resubmit_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Қайта юбориш (Таҳрирлаш) 📝", callback_data=f"mech_resubmit_{request_id}")]
    ])

