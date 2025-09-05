import os
import asyncio
import logging
from dotenv import load_dotenv
from asgiref.sync import sync_to_async
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

from aiogram import Bot as AiogramBot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder

from .models import Bot
from .handlers import create_router  

load_dotenv()
redis_dsn = os.getenv('REDIS_DSN')
redis_jobstore = RedisJobStore(host='localhost', port=6379, db=0)
scheduler = AsyncIOScheduler(
    jobstores={'default': redis_jobstore},
    timezone='Europe/Kyiv'
)

async def setup_bot(bot_obj):
    """
    Створює Aiogram Bot та Dispatcher для одного бота
    """
    bot_instance = AiogramBot(
        token=bot_obj.token,
        default=DefaultBotProperties(parse_mode='HTML')
    )
    await bot_instance.delete_webhook()
    storage = RedisStorage.from_url(redis_dsn, key_builder=DefaultKeyBuilder(with_bot_id=True))
    dp_instance = Dispatcher(storage=storage)
    
    dp_instance.include_router(create_router())
    
    return bot_instance, dp_instance

async def start_all_bots():
    bots = await sync_to_async(list)(Bot.objects.all())
    if not bots:
        logging.warning("Ботів у базі не знайдено!")
        return

    tasks = []
    for bot_obj in bots:
        bot_instance, dp_instance = await setup_bot(bot_obj)
        tasks.append(dp_instance.start_polling(bot_instance))  # bot передається тут

    logging.info(f"Запуск {len(tasks)} ботів...")
    await asyncio.gather(*tasks)

async def setup_and_start(bot: Bot):
    bot_instance, dp_instance = await setup_bot(bot)
    await dp_instance.start_polling(bot_instance)
