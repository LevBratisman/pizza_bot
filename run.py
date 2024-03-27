import os, asyncio, logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from app.middlewares.db import DataBaseSession

from app.database.engine import create_db, drop_db, session_maker
from app.handlers.user_group import user_group_router
from app.handlers.user_private import user_private_router
from app.handlers.admin_private import admin_private_router


bot = Bot(token=os.getenv('BOT_TOKEN'), parse_mode=ParseMode.HTML)
dp = Dispatcher()

bot.my_admins_list = []

dp.include_router(user_group_router)
dp.include_router(user_private_router)
dp.include_router(admin_private_router)


async def on_startup(bot):
    
    run_param = False
    if run_param:
        await drop_db()
    
    await create_db()    


async def on_shutdown(bot):
    print('Бот остановлен')


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    dp.update.middleware(DataBaseSession(session_pool=session_maker))
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("error")