import logging
from asgiref.sync import sync_to_async

from django.utils import timezone
from aiogram import Router
from aiogram.types import Message
from aiogram.filters.command import CommandStart

from .models import User, Bloger, Campain, MessageAfterStart
from .utils import send_message

def create_router():
    router = Router()

    @router.message(CommandStart())
    async def start(message: Message):
        args = message.text.split()
        logging.info('Отримано повідомлення')

        if len(args) > 1:
            ref_code = args[1]

            if ref_code.startswith('ref_'):
                bloger_id = ref_code.split('_')[1]
                bloger = await sync_to_async(Bloger.objects.get)(id=bloger_id)
                bot = await sync_to_async(lambda: bloger.bot)()

                user, created = await sync_to_async(User.objects.get_or_create)(
                    telegram_id=message.from_user.id,
                    bot=bot,
                    defaults={
                        'username': message.from_user.username,
                        'first_name': message.from_user.first_name,
                        'last_name': message.from_user.last_name,
                        'bloger': bloger
                    }
                )

                if created:
                    bloger.invited_people += 1
                    await sync_to_async(bloger.save)()

                    campains = await sync_to_async(lambda: list(Campain.objects.filter(bot=bot)))()
                    for campain in campains:
                        send_time = timezone.now() + timezone.timedelta(minutes=campain.delay_minutes)
                        await sync_to_async(MessageAfterStart.objects.create)(
                            bot=bot,
                            user=user,
                            text=campain.text,
                            button_text=campain.button_text,
                            media=campain.media,
                            send_at=send_time
                        )

                await send_message(message, bloger)

    return router