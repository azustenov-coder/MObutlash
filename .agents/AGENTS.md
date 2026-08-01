# MO Butlash Loyihasi Eslatmalari

## Render Free Tier Limit va Keep-Alive Yechimi
- Render Free Tier oyiga max 750 soat bepul limit beradi.
- Bot 24/7 uzluksiz ishlasa (har 3 minutda ping yuborilsa), limit oyning 24-28-sanalarida tugab, "Suspended by Free Tier Usage Exceeded" beradi.
- Boshliqlar bilan kelishiladigan taklif etilgan yechim:
  - `main.py` ichidagi `keep_alive_loop` ga Toshkent vaqti bo'yicha (UTC+5) ish vaqti cheklovini qo'shish (masalan 08:00 - 22:00 gacha ping, tunda uxlash). Shunda oyiga ~434 soat sarflanib, 750 soatlik limit butun oyga bemalol yetadi.
