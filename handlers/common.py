from aiogram import Router, F
from html import escape
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import re
import time
import database as db

# Kesh: mashina sonlari (DB ga har safar murojaat qilmaslik uchun)
_vehicle_cache = {'soz': 0, 'nosoz': 0, 'total': 0, 'updated_at': 0.0}
_menu_counts_cache: dict[tuple[str, int], tuple[float, dict]] = {}
VEHICLE_CACHE_TTL_SECONDS = 20
MENU_COUNTS_CACHE_TTL_SECONDS = 8

router = Router()

EXCEL_REPORT_BUTTONS = (
    "Excel hisobot yuklab olish 📊",
    "Excel ҳисобот юклаб олиш 📊",
    "Ехсел ҳисобот юклаб олиш 📊",
)

MAIN_MENU_PREFIXES = (
    "Аъзолик сўровлари", "Ходимлар рўйхати", "Кутилаётган заявкалар",
    "Барча заявкалар", "Тугалланмаган заявкалар", "Тугалланган заявкалар",
    "Заявкалар ҳаракати", "Омбор қолдиқлари", "Excel ҳисобот юклаб олиш",
    "Ехсел ҳисобот юклаб олиш",
    "Кунлик ҳисобот", "Соз ҳолат", "Носоз ҳолат", "Автомашиналар",
    "Автолар", "Менинг заявкаларим", "Складдан олиш",
    "Тайёрланиши кутилаётганлар", "Омбор захирасини бошқариш",
    "Етказилиши кутилаётганлар", "Қидирилаётган товарлар",
    "Актив етказувларим", "Склад қабулини кутаётганлар", "Кун якуни",
    "Kutilayotgan zayavkalar", "Barcha zayavkalar", "Ombor qoldiqlari",
    "Excel hisobot yuklab olish", "Kunlik hisobot", "Yetkazilishi kutilayotganlar",
    "Qidirilayotgan tovarlar", "Aktiv yetkazuvlarim", "Sklad qabulini kutayotganlar",
)


def is_main_menu_text(text: str) -> bool:
    return any(text.startswith(prefix) for prefix in MAIN_MENU_PREFIXES)

class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_role = State()

ROLE_LABELS = {
    'manager': 'Boshqaruvchi 💼',
    'observer': 'Boshqaruvchi 2 💼',
    'mechanic': 'Mexanik 🔧',
    'brigadier': 'Brigadir RB 🏭',
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
        'бошқарувчи': 'manager',
        'manager': 'manager',
        'boshqaruvchi 2': 'observer',
        'бошқарувчи 2': 'observer',
        'boshqaruvchi2': 'observer',
        'бошқарувчи2': 'observer',
        'kuzatuvchi': 'observer',
        'observer': 'observer',
        'mexanik': 'mechanic',
        'механик': 'mechanic',
        'mechanic': 'mechanic',
        'brigadir': 'brigadier',
        'бригадир': 'brigadier',
        'brigadir rb': 'brigadier',
        'бригадир рб': 'brigadier',
        'brigadier rb': 'brigadier',
        # Eski yozuv mosligi uchun saqlanadi; bot endi RB deb ko'rsatadi.
        'brigadir br': 'brigadier',
        'brigadier': 'brigadier',
        'yetkazib beruvchi': 'courier',
        'taminotchi': 'courier',
        'таъминотчи': 'courier',
        'taminotchi 🚚': 'courier',
        'kuryer': 'courier',
        'courier': 'courier',
        'skladchik': 'warehouseman',
        'складчик': 'warehouseman',
        'omborchi': 'warehouseman',
        'омборчи': 'warehouseman',
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
    if row:
        keyboard.append(row)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

async def refresh_vehicle_cache(force: bool = False):
    """Mashina sonlarini DB dan yangilash (async, blokirovkasiz)"""
    global _vehicle_cache
    now = time.monotonic()
    if not force and now - _vehicle_cache.get('updated_at', 0.0) < VEHICLE_CACHE_TTL_SECONDS:
        return
    try:
        counts = await db.get_vehicle_counts()
        _vehicle_cache['soz'] = counts.get('soz', 0)
        _vehicle_cache['nosoz'] = counts.get('nosoz', 0)
        _vehicle_cache['total'] = counts.get('total', 0)
        _vehicle_cache['updated_at'] = now
    except Exception:
        pass  # Kesh eski qiymatlarni saqlaydi


async def _get_cached_menu_counts(cache_key: tuple[str, int], loader):
    """Keep rapidly repeated menu presses from hitting PostgreSQL each time."""
    now = time.monotonic()
    cached = _menu_counts_cache.get(cache_key)
    if cached and now - cached[0] < MENU_COUNTS_CACHE_TTL_SECONDS:
        return cached[1]
    counts = await loader()
    _menu_counts_cache[cache_key] = (now, counts)
    return counts

def get_main_keyboard(role: str, soz_count: int = None, nosoz_count: int = None, vehicle_count: int = None, request_counts: dict = None, leadership_counts: dict = None, courier_counts: dict = None):
    # Agar son berilmagan bo'lsa, keshdan olamiz (blokirovkasiz!)
    if soz_count is None:
        soz_count = _vehicle_cache.get('soz', 0)
    if nosoz_count is None:
        nosoz_count = _vehicle_cache.get('nosoz', 0)
    if vehicle_count is None:
        vehicle_count = _vehicle_cache.get('total', 0)
        
    soz_btn_text = f"Соз ҳолат 🟢 ({soz_count})"
    nosoz_btn_text = f"Носоз ҳолат 🔴 ({nosoz_count})"
    vehicles_btn_text = f"Автомашиналар 🚗 ({vehicle_count})"
    request_counts = request_counts or {}
    leadership_counts = leadership_counts or {}
    courier_counts = courier_counts or {}
    membership_btn = f"Аъзолик сўровлари 👥 ({leadership_counts.get('pending_users', 0)})"
    employees_btn = f"Ходимлар рўйхати 📋 ({leadership_counts.get('approved_users', 0)})"
    pending_btn = f"Кутилаётган заявкалар 📥 ({leadership_counts.get('pending_requests', 0)})"
    all_requests_btn = f"Барча заявкалар 📝 ({leadership_counts.get('all_requests', 0)})"
    open_requests_btn = f"Тугалланмаган заявкалар ⏳ ({leadership_counts.get('open_requests', 0)})"
    completed_requests_btn = f"Тугалланган заявкалар ✅ ({leadership_counts.get('completed_requests', 0)})"
    movement_btn = f"Заявкалар ҳаракати 🔄 ({leadership_counts.get('all_requests', 0)})"
    inventory_btn = f"Омбор қолдиқлари 📦 ({leadership_counts.get('inventory_items', 0)})"

    keyboard = []
    if role == 'super_admin':
        keyboard = [
            [KeyboardButton(text=membership_btn), KeyboardButton(text=employees_btn)],
            [KeyboardButton(text=pending_btn), KeyboardButton(text=all_requests_btn)],
            [KeyboardButton(text=open_requests_btn), KeyboardButton(text=vehicles_btn_text)],
            [KeyboardButton(text=completed_requests_btn)],
            [KeyboardButton(text=movement_btn), KeyboardButton(text=inventory_btn)],
            [KeyboardButton(text="Excel ҳисобот юклаб олиш 📊"), KeyboardButton(text="Кунлик ҳисобот 📅")],
            [KeyboardButton(text=soz_btn_text), KeyboardButton(text=nosoz_btn_text)]
        ]
    elif role == 'manager':
        keyboard = [
            [KeyboardButton(text=pending_btn)],
            [KeyboardButton(text=all_requests_btn), KeyboardButton(text=employees_btn)],
            [KeyboardButton(text=open_requests_btn), KeyboardButton(text=vehicles_btn_text)],
            [KeyboardButton(text=completed_requests_btn)],
            [KeyboardButton(text=movement_btn), KeyboardButton(text=inventory_btn)],
            [KeyboardButton(text="Excel ҳисобот юклаб олиш 📊"), KeyboardButton(text="Кунлик ҳисобот 📅")],
            [KeyboardButton(text=soz_btn_text), KeyboardButton(text=nosoz_btn_text)]
        ]
    elif role == 'observer':
        keyboard = [
            [KeyboardButton(text=f"Kutilayotgan zayavkalar 📥 ({leadership_counts.get('pending_requests', 0)})")],
            [KeyboardButton(text=all_requests_btn), KeyboardButton(text=employees_btn)],
            [KeyboardButton(text=open_requests_btn), KeyboardButton(text=vehicles_btn_text)],
            [KeyboardButton(text=completed_requests_btn)],
            [KeyboardButton(text=movement_btn), KeyboardButton(text=inventory_btn)],
            [KeyboardButton(text="Excel ҳисобот юклаб олиш 📊"), KeyboardButton(text="Кунлик ҳисобот 📅")],
            [KeyboardButton(text=soz_btn_text), KeyboardButton(text=nosoz_btn_text)]
        ]
    elif role in ['mechanic', 'brigadier']:
        my_requests_btn = "Менинг заявкаларим 📂"
        unfinished_btn = "Тугалланмаган заявкалар ⏳"
        completed_btn = "Тугалланган заявкалар ✅"
        if request_counts:
            my_requests_btn += f" ({request_counts.get('total', 0)})"
            unfinished_btn += f" ({request_counts.get('unfinished', 0)})"
            completed_btn += f" ({request_counts.get('completed', 0)})"
            pickup_btn = f"Складдан олиш 📦 ({request_counts.get('ready_for_pickup', 0)})"
        else:
            pickup_btn = "Складдан олиш 📦"
        keyboard = [
            [KeyboardButton(text=soz_btn_text), KeyboardButton(text=nosoz_btn_text)],
            [KeyboardButton(text=f"Автолар 🚗 ({vehicle_count})"), KeyboardButton(text=my_requests_btn)],
            [KeyboardButton(text=unfinished_btn), KeyboardButton(text=pickup_btn)],
            [KeyboardButton(text=completed_btn)]
        ]
    elif role == 'warehouseman':
        keyboard = [
            [KeyboardButton(text="Тайёрланиши кутилаётганлар 📦"), KeyboardButton(text="Омбор захирасини бошқариш ⚙️")],
            [KeyboardButton(text="Барча заявкалар 📝"), KeyboardButton(text="Омбор қолдиқлари 📦")],
            [KeyboardButton(text="Excel ҳисобот юклаб олиш 📊"), KeyboardButton(text="Кунлик ҳисобот 📅")]
        ]
    elif role == 'courier':
        if courier_counts:
            return ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text=f"Yetkazilishi kutilayotganlar \U0001F69A ({courier_counts.get('available', 0)})"), KeyboardButton(text=f"Qidirilayotgan tovarlar \U0001F50E ({courier_counts.get('searching_items', 0)})")],
                    [KeyboardButton(text=f"Aktiv yetkazuvlarim \U0001F6E3\uFE0F ({courier_counts.get('active', 0)})"), KeyboardButton(text=f"Sklad qabulini kutayotganlar \U0001F4E6 ({courier_counts.get('awaiting_receipt', 0)})")],
                    [KeyboardButton(text="Kun yakuni \U0001F4CA")],
                ],
                resize_keyboard=True,
            )
        keyboard = [
            [KeyboardButton(text="Етказилиши кутилаётганлар 🚚"), KeyboardButton(text="Қидирилаётган товарлар 🔎")],
            [KeyboardButton(text="Актив етказувларим 🛣️"), KeyboardButton(text="Кун якуни 📊")]
        ]
    
    if not keyboard:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


async def get_user_main_keyboard(telegram_id: int, role: str):
    """Build a fresh role keyboard with current PostgreSQL counters."""
    request_counts = None
    leadership_counts = None
    courier_counts = None
    if role in ['mechanic', 'brigadier']:
        _, request_counts = await asyncio.gather(
            refresh_vehicle_cache(),
            _get_cached_menu_counts(
                ('requests', telegram_id),
                lambda: db.get_user_request_counts(telegram_id),
            ),
        )
    elif role in ['super_admin', 'manager', 'observer']:
        _, leadership_counts = await asyncio.gather(
            refresh_vehicle_cache(),
            _get_cached_menu_counts(
                ('leadership', 0), db.get_leadership_menu_counts
            ),
        )
    elif role == 'courier':
        _, courier_counts = await asyncio.gather(
            refresh_vehicle_cache(),
            _get_cached_menu_counts(
                ('courier', telegram_id),
                lambda: db.get_courier_menu_counts(telegram_id),
            ),
        )
    else:
        await refresh_vehicle_cache()
    return get_main_keyboard(
        role,
        request_counts=request_counts,
        leadership_counts=leadership_counts,
        courier_counts=courier_counts,
    )


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
            role_text = "Super Admin"
        await message.answer(
            f"👋 Хуш келибсиз, {user['full_name']}!\n"
            f"🔑 Сизнинг ролингиз: {role_text}",
            reply_markup=await get_user_main_keyboard(telegram_id, user['role'])
        )
    else:
        await message.answer(
            "⏳ Sizning so'rovingiz hali ko'rib chiqilmoqda. Admin tasdiqlashini kuting.",
            reply_markup=ReplyKeyboardRemove()
        )

# /menu komandasi
@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сиз ҳали рўйхатдан ўтмагансиз. /start босинг.")
        return
    if user['is_approved'] != 1:
        await message.answer("Сиз ҳали тасдиқланмагансиз. Админ тасдиқлашини кутинг.")
        return
    role_text = ROLE_LABELS.get(user['role'], user['role'])
    if user['role'] == 'super_admin':
        role_text = "Super Admin"
    await message.answer(
        f"🔄 Меню янгиланди!\n🔑 Ролингиз: {role_text}",
        reply_markup=await get_user_main_keyboard(message.from_user.id, user['role'])
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
@router.message(F.text.in_(EXCEL_REPORT_BUTTONS))
async def download_excel_report(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager', 'warehouseman', 'observer']:
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


# Kunlik Excel hisoboti yuklab olish
@router.message(F.text.in_(["Kunlik hisobot 📅", "Кунлик ҳисобот 📅"]))
async def download_daily_excel_report(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager', 'warehouseman', 'observer']:
        await message.answer("Сизда ҳисобот юклаб олиш ҳуқуқи йўқ.")
        return
        
    await message.answer("Кунлик ҳисобот тайёрланмоқда, илтимос кутинг... ⏳")
    try:
        from aiogram.types import FSInputFile
        file_path = await db.export_daily_report_to_excel()
        await message.answer_document(
            document=FSInputFile(file_path),
            caption="📅 Кунлик омбор қолдиқлари va бугунги ҳаракатлар (кирим/чиқим) ҳисоботи"
        )
    except Exception as e:
        await message.answer(f"Ҳисобот яратишда хатолик юз берди: {e}")

def build_inventory_table(stock: list[dict]) -> list[str]:
    """Return Telegram-safe, fixed-width inventory table chunks."""
    lines = ["№   Toifa        Mahsulot                     Miqdor"]
    for index, item in enumerate(stock, start=1):
        category = 'Tayyor' if item.get('category') == 'tayyor' else 'Butlovchi'
        name = str(item['name']).replace('\n', ' ')[:28]
        lines.append(f"{index:<3} {category:<12} {name:<28} {item['quantity']:>5} dona")

    chunks, current = [], []
    for line in lines:
        candidate = '\n'.join(current + [line])
        if len(candidate) > 3300 and current:
            chunks.append('<pre>' + escape('\n'.join(current)) + '</pre>')
            current = [lines[0], line]
        else:
            current.append(line)
    if current:
        chunks.append('<pre>' + escape('\n'.join(current)) + '</pre>')
    return chunks


# Ombor qoldiqlari ro'yxatini ko'rish
@router.message(F.text.in_(["Ombor qoldiqlari 📦", "Омбор қолдиқлари 📦"]) | F.text.startswith("Ombor qoldiqlari 📦") | F.text.startswith("Омбор қолдиқлари 📦"))
async def show_warehouse_stock(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user['role'] not in ['super_admin', 'manager', 'warehouseman', 'observer']:
        await message.answer("Сизда ушбу маълумотни кўриш ҳуқуқи йўқ.")
        return
        
    stock = await db.get_all_inventory()
    if not stock:
        await message.answer("Омбор бўш. Ҳозирча ҳеч қандай маҳсулот мавжуд эмас.")
        return
        
    try:
        from aiogram.types import FSInputFile
        file_path = await db.export_inventory_to_excel()
        await message.answer_document(
            document=FSInputFile(file_path),
            caption="📊 Омбор қолдиқлари — Excel ҳисоботи",
        )
    except Exception as e:
        await message.answer(f"Excel jadvalini yaratishda xatolik: {e}")
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
def get_courier_action_keyboard(request_id: int, request_type: str = 'purchase'):
    if request_type == 'repair':
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔎 Қидиряпман", callback_data=f"cour_search_{request_id}"),
                InlineKeyboardButton(text="📦 Топширдим", callback_data=f"cour_handover_{request_id}")
            ]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔎 Қидиряпман", callback_data=f"cour_search_{request_id}"),
                InlineKeyboardButton(text="🛒 Сотиб олдим", callback_data=f"cour_buy_{request_id}")
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


def get_mechanic_pickup_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Складдан oldim ✅", callback_data=f"mech_pickup_{request_id}")]
    ])

# Mexanik uchun zayavkani qayta ishlash/tahrirlash tugmasi
def get_mechanic_resubmit_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Қайта юбориш (Таҳрирлаш) 📝", callback_data=f"mech_resubmit_{request_id}")]
    ])

