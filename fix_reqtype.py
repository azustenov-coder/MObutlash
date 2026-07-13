import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('handlers/mechanic.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add new states after waiting_for_photo
old_states = """class RequestCreationStates(StatesGroup):
    waiting_for_vehicle = State()
    waiting_for_photo = State()
    waiting_for_items_text = State()"""

new_states = """class RequestCreationStates(StatesGroup):
    waiting_for_vehicle = State()
    waiting_for_photo = State()
    waiting_for_requester = State()
    waiting_for_request_type = State()
    waiting_for_items_text = State()"""

content = content.replace(old_states, new_states, 1)

# 2. Replace photo handler ending (go to requester instead of items_text)
old_photo_end = """    await state.update_data(old_part_photo=photo_id)
    await state.set_state(RequestCreationStates.waiting_for_items_text)
    
    cancel_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="\u0411\u0435\u043a\u043e\u0440 \u049b\u0438\u043b\u0438\u0448 \u274c")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(
        "\U0001f4dd **\u0417\u0430\u044f\u0432\u043a\u0430 \u0442\u0430\u0440\u043a\u0438\u0431\u0438\u0434\u0430\u0433\u0438 \u043c\u0430\u04b3\u0441\u0443\u043b\u043e\u0442\u043b\u0430\u0440 \u0432\u0430 \u0442\u0430\u044a\u043c\u0438\u0440lashlarni yozing:**\\n"
        "\u041c\u0430\u0441\u0430\u043b\u0430\u043d:\\n"
        "- `2 ta balon`\\n"
        "- `4 ta pachivnik`\\n"
        "- `generatorni sozlash`\\n\\n"
        "(Hammasini bitta xabarda yozishingiz mumkin, tizim avtomatik ajratadi)",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )

@router.message(RequestCreationStates.waiting_for_items_text)"""

new_photo_end = """    await state.update_data(old_part_photo=photo_id)
    await state.set_state(RequestCreationStates.waiting_for_requester)
    
    cancel_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="\u0411\u0435\u043a\u043e\u0440 \u049b\u0438\u043b\u0438\u0448 \u274c")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(
        "\U0001f464 **Kim so'rayapti?**\\n"
        "Buyurtmachining ismi yoki lavozimini yozing:\\n"
        "(Masalan: `Ivanov Ivan`, `Brigadir`, `\u04b2aydovchi`)",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )

@router.message(RequestCreationStates.waiting_for_requester)
async def process_requester(message: Message, state: FSMContext):
    if message.text == "\u0411\u0435\u043a\u043e\u0440 \u049b\u0438\u043b\u0438\u0448 \u274c":
        user = await db.get_user(message.from_user.id)
        await state.clear()
        await message.answer("\u0417\u0430\u044f\u0432\u043a\u0430 \u0431\u0435\u043a\u043e\u0440 \u049b\u0438\u043b\u0438\u043d\u0434\u0438.", reply_markup=get_main_keyboard(user['role']))
        return
    
    if not message.text:
        await message.answer("\u0418\u043b\u0442\u0438\u043c\u043e\u0441, \u0438\u0441\u043c \u0451\u043a\u0438 \u043b\u0430\u0432\u043e\u0437\u0438\u043c \u0451\u0437\u0438\u043d\u0433:")
        return
    
    await state.update_data(requester_name=message.text.strip())
    await state.set_state(RequestCreationStates.waiting_for_request_type)
    
    type_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\U0001f6e0 Tamirlash", callback_data="reqtype_repair"),
            InlineKeyboardButton(text="\U0001f6d2 Yangi zapchast", callback_data="reqtype_purchase")
        ],
        [InlineKeyboardButton(text="\u274c Bekor qilish", callback_data="reqtype_cancel")]
    ])
    
    await message.answer(
        "\U0001f4cb **Zayvka turini tanlang:**",
        reply_markup=type_kb,
        parse_mode="Markdown"
    )

@router.callback_query(RequestCreationStates.waiting_for_request_type, F.data.startswith("reqtype_"))
async def process_request_type(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    
    if action == "cancel":
        user = await db.get_user(callback.from_user.id)
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("\u0417\u0430\u044f\u0432\u043a\u0430 \u0431\u0435\u043a\u043e\u0440 \u049b\u0438\u043b\u0438\u043d\u0434\u0438.", reply_markup=get_main_keyboard(user['role']))
        await callback.answer()
        return
    
    req_type = "repair" if action == "repair" else "purchase"
    await state.update_data(forced_request_type=req_type)
    await state.set_state(RequestCreationStates.waiting_for_items_text)
    
    cancel_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="\u0411\u0435\u043a\u043e\u0440 \u049b\u0438\u043b\u0438\u0448 \u274c")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    if req_type == "repair":
        prompt = (
            "\U0001f6e0 **Tamirlash zayvkasi**\\n\\n"
            "\U0001f4dd Tamirlash kerak bo'lgan narsalarni yozing:\\n"
            "(Masalan: `generatorni sozlash`, `tormoz yo'gini almashtirish`)"
        )
    else:
        prompt = (
            "\U0001f6d2 **Yangi zapchast zayvkasi**\\n\\n"
            "\U0001f4dd Kerakli zapchastlar ro'yxatini yozing:\\n"
            "(Masalan: `2 ta balon`, `4 ta pachivnik`, `1 ta filtr`)"
        )
    
    await callback.answer()
    await callback.message.edit_text(prompt, parse_mode="Markdown")
    await callback.message.answer("\u2b07\ufe0f Yozing:", reply_markup=cancel_kb)

@router.message(RequestCreationStates.waiting_for_items_text)"""

content = content.replace(old_photo_end, new_photo_end, 1)

# 3. Override item type with forced_request_type in process_items_text
old_items = """    text = message.text.strip()
    parsed_items = await parse_request_text(text)"""

new_items = """    text = message.text.strip()
    state_data = await state.get_data()
    forced_type = state_data.get('forced_request_type', None)
    parsed_items = await parse_request_text(text)"""

content = content.replace(old_items, new_items, 1)

old_items_store = """    await state.update_data(temp_items=parsed_items)
    await show_loop_decision(message, state)"""

new_items_store = """    if forced_type:
        for item in parsed_items:
            item['type'] = forced_type
    await state.update_data(temp_items=parsed_items)
    await show_loop_decision(message, state)"""

content = content.replace(old_items_store, new_items_store, 1)

with open('handlers/mechanic.py', 'w', encoding='utf-8') as f:
    f.write(content)

with open('handlers/mechanic.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
print('Done! Lines:', len(lines))
