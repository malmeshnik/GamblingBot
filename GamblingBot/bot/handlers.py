import asyncio
import logging
import mimetypes
from asgiref.sync import sync_to_async

from django.utils import timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters.command import CommandStart

from .models import User, Bloger, Campain, MessageAfterStart, Bot, Message as DbMessage
from .utils import send_message
from .sender import send_message_safe, get_keyboard

DIGITS = ["🕔 5", "🕔 4", "🕔 3", "🕔 2", "🕔 1"]


def create_router():
    router = Router()

    @router.message(CommandStart())
    async def start(message: Message):
        args = message.text.split()
        logging.info("Отримано повідомлення")

        if len(args) > 1:
            ref_code = args[1]

            if ref_code.startswith("ref_"):
                bloger_id = ref_code.split("_")[1]
                bloger = await sync_to_async(Bloger.objects.get)(id=bloger_id)
                bot = await sync_to_async(lambda: bloger.bot)()

                user, created = await sync_to_async(User.objects.get_or_create)(
                    telegram_id=message.from_user.id,
                    bot=bot,
                    defaults={
                        "username": message.from_user.username,
                        "first_name": message.from_user.first_name,
                        "last_name": message.from_user.last_name,
                        "bloger": bloger,
                    },
                )

                if created:
                    bloger.invited_people += 1
                    await sync_to_async(bloger.save)()

                    if bot.use_our_messages:
                        campains = await sync_to_async(
                            lambda: list(Campain.objects.filter(bot=bot))
                        )()
                    else:
                        campains = await sync_to_async(
                            lambda: list(Campain.objects.filter(folder=bot.folder))
                        )()
                    for campain in campains:
                        send_time = timezone.now() + timezone.timedelta(
                            minutes=campain.delay_minutes
                        )
                        print(f"time to sent message: {send_time}")
                        await sync_to_async(MessageAfterStart.objects.create)(
                            bot=bot,
                            user=user,
                            text=campain.text,
                            button_text=campain.button_text,
                            media=campain.media,
                            send_at=send_time,
                        )

                await send_message(message, bloger)

    @router.callback_query(F.data == "send_digits")
    async def send_digits(query: CallbackQuery):
        user_id = query.message.chat.id
        bot_id = query.message.bot.id

        bot = await sync_to_async(Bot.objects.get)(bot_id=bot_id)
        user = await sync_to_async(
            User.objects.filter(bot=bot, telegram_id=user_id).first
        )()

        if bot.use_our_messages:
            messages = await sync_to_async(list)(
                DbMessage.objects.filter(bot=bot, message_for_digits=True)
            )()
        else:
            folder = await sync_to_async(lambda: bot.folder)()
            messages = await sync_to_async(list)(
                DbMessage.objects.filter(folder=folder, message_for_digits=True)
            )

        await query.message.delete()
        first_message = messages[0]
        keyboard = None
        media_file = (
            FSInputFile(first_message.media.path) if first_message.media else None
        )
        mime, _ = (
            mimetypes.guess_type(first_message.media.path)
            if first_message.media
            else (None, None)
        )
        msg = await send_message_safe(
            bot.token, user, first_message.text, keyboard, media_file, mime
        )
        for message in messages[1:]:
            await asyncio.sleep(2)
            msg = await msg.edit_text(message.text)

        for digit in DIGITS:
            await asyncio.sleep(1)
            msg = await msg.edit_text(digit)

        await msg.delete()
        if bot.use_our_messages:
            main_message = await sync_to_async(
                DbMessage.objects.filter(bot=bot, message_for_digits=False, send_digits=False).first
            )()
        else:
            main_message = await sync_to_async(
                DbMessage.objects.filter(folder=await sync_to_async(lambda: bot.folder)(), message_for_digits=False, send_digits=False).first
            )()
        keyboard = get_keyboard(main_message.button_text, await sync_to_async(lambda: user.bloger.ref_link_to_site)())
        media_file = (
            FSInputFile(main_message.media.path) if main_message.media else None
        )
        mime, _ = (
            mimetypes.guess_type(main_message.media.path)
            if main_message.media
            else (None, None)
        )
        msg = await send_message_safe(
            bot.token, user, main_message.text, keyboard, media_file, mime
        )

    return router
