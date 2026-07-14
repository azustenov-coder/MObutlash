# MO Butlash Bot — Telegram zayavka boshqaruv tizimi

Python + aiogram v3 yordamida yozilgan ko'p rollli Telegram bot.

## Rollar
| № | Rol | Vakolat |
|---|-----|---------|
| 1 | Super Admin | Barcha huquqlar, foydalanuvchilarni tasdiqlash |
| 2 | Boshqaruvchi 💼 | Zayavkalarni tasdiqlash, sklardan chiqarishga ruxsat berish |
| 3 | Boshqaruvchi 2 💼 | Faqat kuzatish |
| 4 | Mexanik 🔧 | Zayavka yaratish |
| 5 | Brigadir RB 🚜 | Zayavka yaratish |
| 6 | Ta'minotchi 🚚 | Yetkazib berish |
| 7 | Skladchik 📦 | Ombor boshqarish, qabul qilish |

## O'rnatish

```bash
# 1. Virtual muhit yaratish
python -m venv .venv
.venv\Scripts\activate

# 2. Kutubxonalarni o'rnatish
pip install aiogram python-dotenv aiosqlite openpyxl

# 3. .env faylini sozlash
# .env.example ni nusxalab .env yarating
cp .env.example .env
# BOT_TOKEN va ADMIN_ID ni to'ldiring

# 4. Botni ishga tushirish
python main.py
```

## `.env` fayli namunasi
```
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_ID=your_telegram_user_id_here
```

## Loyiha tuzilmasi
```
MObutlash/
├── main.py              # Bot asosiy fayli
├── config.py            # Konfiguratsiya
├── database.py          # SQLite ma'lumotlar bazasi
├── handlers/
│   ├── common.py        # Umumiy handlerlar (start, menu)
│   ├── admin.py         # Admin handlerlari
│   ├── controller.py    # Boshqaruvchi handlerlari
│   ├── mechanic.py      # Mexanik handlerlari
│   └── assembler.py     # Brigadir/Kuryer handlerlari
└── .gitignore
```
