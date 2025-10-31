import asyncio
import logging
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from django.core.management.base import BaseCommand
from bot.bot_instance import scheduler, start_all_bots
from bot.sender import send_scheduled_messages, send_messages_after_start

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.getLogger("apscheduler").setLevel(logging.INFO)

class Command(BaseCommand):
    help = "run aiogram bot"

    def handle(self, *args, **options):
        async def main():
            # Очистити старі джоби щоб уникнути дублювання
            try:
                scheduler.remove_all_jobs()
            except Exception:
                pass

            # Конфігурація планувальника — використовуємо AsyncIOExecutor
            scheduler.configure(
                {
                    'apscheduler.jobstores.default': {
                        'type': 'memory'
                    },
                    'apscheduler.executors.default': {
                        # AsyncIOExecutor НЕ приймає параметр max_workers
                        'class': 'apscheduler.executors.asyncio:AsyncIOExecutor'
                    },
                    'apscheduler.job_defaults.coalesce': True,
                    'apscheduler.job_defaults.max_instances': 1,
                    'apscheduler.job_defaults.misfire_grace_time': 60,
                    'apscheduler.timezone': pytz.timezone('Europe/Kiev')
                }
            )

            # Додаємо джоби з унікальними ID (replace_existing щоб не створювались дублікати)
            scheduler.add_job(
                send_scheduled_messages,
                "interval",
                minutes=1,
                id='scheduled_messages',
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                misfire_grace_time=60
            )

            scheduler.add_job(
                send_messages_after_start,
                "interval",
                minutes=1,
                id='messages_after_start',
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                misfire_grace_time=60,
                # можна відсунути старт другої задачі, щоб уникнути синхронного старту
                next_run_time=None
            )

            scheduler.start()
            logging.info("✅ Планувальник запущено")
            logging.info(f"📋 Активні завдання: {[job.id for job in scheduler.get_jobs()]}")
            await start_all_bots()

        asyncio.run(main())
