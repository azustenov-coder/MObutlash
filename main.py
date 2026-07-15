import asyncio
import logging
from logging.handlers import RotatingFileHandler
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.types import TelegramObject, ReplyKeyboardRemove
from typing import Callable, Awaitable, Any, Dict

import config
import database as db
from fsm_storage import PostgresFSMStorage
from text_utils import cyrillize_telegram_payload
from handlers import common, admin, controller, mechanic, assembler, user_management

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"


def configure_logging() -> None:
    """Write current logs to rotating files while keeping console output."""
    formatter = logging.Formatter(LOG_FORMAT)
    all_log = RotatingFileHandler(
        "bot-run.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    all_log.setLevel(logging.INFO)
    all_log.setFormatter(formatter)
    error_log = RotatingFileHandler(
        "bot-run-error.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    error_log.setLevel(logging.ERROR)
    error_log.setFormatter(formatter)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logging.basicConfig(
        level=logging.INFO,
        handlers=[console, all_log, error_log],
        force=True,
    )


configure_logging()

# Handlerlar bildirishnoma yuborish uchun ushbu obyektni import qiladi.
bot: Bot | None = None


class CyrillicBot(Bot):
    """Ensure every user-visible outgoing bot text is Uzbek Cyrillic."""

    async def __call__(self, method, request_timeout=None):
        method = cyrillize_telegram_payload(method)
        return await super().__call__(method, request_timeout=request_timeout)

class AutoRefreshMenuMiddleware(BaseMiddleware):
    """
    Har bir xabar kelganda, foydalanuvchi tasdiqlangan va ro'yxatda bo'lsa,
    uning menyusini avtomatik to'g'ri holatda ko'rsatib turadi.
    Shu bilan birga /start bosmasdan ham menyu doim yangilanib turadi.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Foydalanuvchi ma'lumotini olish
        from aiogram.types import Message, CallbackQuery
        
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
 
        if user_id:
            try:
                user = await db.get_user(user_id)
            except Exception as e:
                logging.warning(f"DB get_user xatosi, qayta urinilmoqda: {e}")
                try:
                    user = await db.get_user(user_id)
                except Exception as e2:
                    logging.error(f"DB get_user 2-urinish ham muvaffaqiyatsiz: {e2}")
                    user = None
            if user and user['is_approved'] == 1:
                # Foydalanuvchi ma'lumotini `data` ga qo'shamiz (handlerlar ishlatishi uchun)
                data['db_user'] = user
 
        return await handler(event, data)


class MainMenuStateResetMiddleware(BaseMiddleware):
    """Close an unfinished dialog when a persistent main-menu button is pressed."""

    async def __call__(self, handler, event, data):
        from aiogram.types import Message

        if isinstance(event, Message) and common.is_main_menu_text(event.text or ""):
            state = data.get("state")
            if state is not None:
                await state.clear()
        return await handler(event, data)
 
 
async def main():
    global bot
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("BOT_TOKEN is not configured")

    bot = CyrillicBot(token=config.BOT_TOKEN)

    # Ma'lumotlar bazasini ishga tushirish
    await db.init_db()
 
    # Dispatcher va xotira omborini sozlash
    dp = Dispatcher(
        storage=PostgresFSMStorage(),
        events_isolation=SimpleEventIsolation(),
    )
 
    # Avtomatik yangilanish middleware'ni ro'yxatdan o'tkazish
    dp.message.outer_middleware(MainMenuStateResetMiddleware())
    dp.message.middleware(AutoRefreshMenuMiddleware())
    dp.callback_query.middleware(AutoRefreshMenuMiddleware())
 
    # Routerlarni ulash
    dp.include_router(user_management.router)
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(controller.router)
    dp.include_router(mechanic.router)
    dp.include_router(assembler.router)

    # Botga /start va /menu komandalarini belgilash
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="Ботни ишга тушириш / Менюни очиш"),
        BotCommand(command="menu", description="Менюни янгилаш"),
    ])

    # Dummy web server function
    async def handle_ping(request):
        return web.Response(text="Bot is running!")

    app = web.Application()
    app.router.add_get("/", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    # Start web server
    await site.start()
    logging.info(f"Dummy web server started on port {port}")

    # Pollingni boshlash
    logging.info("Bot ishga tushmoqda...")
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Botni ishga tushirishda xato yuz berdi: {e}")
    finally:
        await bot.session.close()
        await db.close_db()
        await runner.cleanup()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
