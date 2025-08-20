import asyncio 
import logging

from django.core.management.base import BaseCommand

from bot.handlers import router
from bot.bot_instance import dp, bot, scheduler
from bot.sender import send_scheduled_messages, send_messages_after_start

logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class Command(BaseCommand):
    help = 'run aiogram bot'

    def handle(self, *args, **options):
        dp.include_router(router)

        async def main():
            
            scheduler.add_job(send_scheduled_messages, 'interval', minutes=1)
            scheduler.add_job(send_messages_after_start, 'interval', minutes=1)
            scheduler.start()

            logging.info("Бот і планувальник запущені ✅")

            await dp.start_polling(bot)

        asyncio.run(main())
