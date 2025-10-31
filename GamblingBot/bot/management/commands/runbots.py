import asyncio
import logging

from django.core.management.base import BaseCommand
from bot.bot_instance import scheduler, start_all_bots
from bot.sender import send_scheduled_messages, send_messages_after_start

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.getLogger("apscheduler").setLevel(logging.WARNING)


class Command(BaseCommand):
    help = "run aiogram bot"

    def handle(self, *args, **options):

        async def main():
            # додаємо джоби
            scheduler.add_job(
                send_scheduled_messages,
                "interval",
                minutes=1,
                max_instances=1,
                coalesce=True,
            )
            scheduler.add_job(send_messages_after_start, "interval", minutes=1)

            scheduler.start()
            logging.info("планувальник запущені ✅")
            await start_all_bots()

        asyncio.run(main())
