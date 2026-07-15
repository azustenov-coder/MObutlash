# MO Butlash Telegram boti

Aiogram 3 va PostgreSQL/Neon asosidagi ko‘p rolli zayavka, ta’minot va ombor boshqaruv tizimi.

## Rollar

| Rol | Asosiy vakolat |
|---|---|
| Super admin | Barcha nazorat, a’zolik, xodimlar, zayavkalar va hisobotlar |
| Boshqaruvchi | A’zolik va zayavkalarni tekshirish/tasdiqlash, monitoring |
| Boshqaruvchi 2 | Boshqaruvchi bilan teng huquqli ikkinchi rahbar |
| Mexanik | Avtomobil bo‘yicha zayavka yaratish va ishni rasm bilan yopish |
| Brigadir RB | Mexanik bilan bir xil operatsion jarayon |
| Ta’minotchi | Xarid zayavkasini olish, qidirish, narx kiritish va omborga topshirish |
| Omborchi | Mahsulotni qabul qilish, qoldiq va rasxodni boshqarish |

## Zayavka oqimlari

- Ta’mirlash: mexanik/brigadir → boshqaruvchi ruxsati → mexanik bajaradi → rasm → yakun.
- Ehtiyot qism xaridi: mexanik/brigadir → boshqaruvchi ruxsati → ta’minotchi → omborchi → mexanik o‘rnatadi → rasm → yakun.
- Boshqaruvchi va Boshqaruvchi 2 a’zolik so‘rovlarini ham tekshirishi mumkin.

## Ishga tushirish

```powershell
cd C:\Users\Azizbek\Desktop\MObutlash
.\.venv\Scripts\python.exe main.py
```

`.env` fayli:

```env
BOT_TOKEN=telegram_bot_token
ADMIN_ID=telegram_user_id
DATABASE_URL=postgresql_connection_string
```

Bot `bot-run.log` va `bot-run-error.log` fayllariga aylanma log yozadi. FSM suhbat holatlari PostgreSQL’dagi `bot_fsm` jadvalida saqlanadi, shuning uchun restartdan keyin davom etadi.

## Tekshiruv

```powershell
.\.venv\Scripts\python.exe test_ast.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
