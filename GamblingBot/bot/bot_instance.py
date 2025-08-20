import os
from dotenv import load_dotenv

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
redis_dsn = os.getenv('REDIS_DSN')
scheduler = AsyncIOScheduler(
    jobstores={
        'default': RedisJobStore(host='localhost', port=6379, db=0)
    },
    timezone='Europe/Kyiv'
)

storage = RedisStorage.from_url(redis_dsn, key_builder=DefaultKeyBuilder(with_bot_id=True))

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=storage)