import logging
import mimetypes
from asgiref.sync import sync_to_async

from aiogram import Bot
from aiogram.types import Message, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import Bloger, User, Message as DBMessage


def get_first_message(bloger):
    if bloger:
        if bloger.bot.use_our_messages:
            msg = DBMessage.objects.filter(
                bot=bloger.bot, message_for_digits=False
            ).first()
        else:
            msg = DBMessage.objects.filter(
                folder=bloger.bot.folder, message_for_digits=False
            ).first()

        return msg


async def send_message(message: Message, bloger: Bloger, msg_db: DBMessage = None):
    try:
        msg = await sync_to_async(get_first_message)(bloger)
        if msg_db:
            callback_data = "accept_terms"
        elif msg.send_digits:
            callback_data = "send_digits"
        else:
            callback_data = None

        msg = msg_db if msg_db else msg

        keyboard = await get_keyboard(
            msg.button_text, bloger.ref_link_to_site if bloger else None, callback_data
        )

        if msg.media:
            mime, _ = mimetypes.guess_type(msg.media.path)
            file = FSInputFile(msg.media.path)

            if "image" in mime:
                await message.answer_photo(
                    photo=file,
                    caption=msg.text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            elif "video" in mime:
                await message.answer_video(
                    video=file,
                    caption=msg.text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            else:
                await message.answer_document(
                    document=file,
                    caption=msg.text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        else:
            await message.answer(
                text=msg.text, reply_markup=keyboard, parse_mode="HTML"
            )

    except Exception as e:
        logging.error(f"Error sending message: {e}")


async def get_keyboard(text: str, link: str, callback_data: str = None):
    kb = InlineKeyboardBuilder()

    if callback_data:
        kb.button(text=text, callback_data=callback_data)
    else:
        kb.button(text=text, url=link)

    return kb.as_markup()


async def check_bot(token: str):
    try:
        async with Bot(token) as bot:
            bot_info = await bot.get_me()
    except Exception as e:
        return e

    return bot_info
