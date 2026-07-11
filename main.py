import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, ReplyKeyboardRemove
from typing import Callable, Awaitable, Any, Dict

import config
import database as db
from handlers import common, admin, controller, mechanic, assembler

# Bot loglarini sozlash
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Global bot obyekti
bot = Bot(token=config.BOT_TOKEN)


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
            user = await db.get_user(user_id)
            if user and user['is_approved'] == 1:
                # Foydalanuvchi ma'lumotini `data` ga qo'shamiz (handlerlar ishlatishi uchun)
                data['db_user'] = user

        return await handler(event, data)


async def main():
    # Ma'lumotlar bazasini ishga tushirish
    await db.init_db()

    # Dispatcher va xotira omborini sozlash
    dp = Dispatcher(storage=MemoryStorage())

    # Avtomatik yangilanish middleware'ni ro'yxatdan o'tkazish
    dp.message.middleware(AutoRefreshMenuMiddleware())
    dp.callback_query.middleware(AutoRefreshMenuMiddleware())

    # Routerlarni ulash
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

    # Pollingni boshlash
    logging.info("Bot ishga tushmoqda...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Botni ishga tushirishda xato yuz berdi: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
