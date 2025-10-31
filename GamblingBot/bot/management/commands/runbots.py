import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from django.core.management.base import BaseCommand
from bot.bot_instance import scheduler, start_all_bots
from bot.sender import send_scheduled_messages, send_messages_after_start

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

class Command(BaseCommand):
    help = "run aiogram bot"

    def handle(self, *args, **options):
        async def main():
            # Налаштування планувальника
            scheduler.configure(
                {
                    'apscheduler.jobstores.default': {
                        'type': 'memory'
                    },
                    'apscheduler.executors.default': {
                        'class': 'apscheduler.executors.pool:ThreadPoolExecutor',
                        'max_workers': '1'
                    },
                    'apscheduler.job_defaults.coalesce': True,
                    'apscheduler.job_defaults.max_instances': 1,
                    'apscheduler.timezone': 'UTC'
                }
            )

            # Додаємо джоби з унікальними ID
            scheduler.add_job(
                send_scheduled_messages,
                "interval",
                minutes=1,
                id='scheduled_messages',
                replace_existing=True,
                coalesce=True,
                max_instances=1
            )
            
            scheduler.add_job(
                send_messages_after_start,
                "interval",
                minutes=1,
                id='messages_after_start',
                replace_existing=True,
                coalesce=True,
                max_instances=1
            )

            scheduler.start()
            logging.info("✅ Планувальник запущено")
            await start_all_bots()

        asyncio.run(main())
