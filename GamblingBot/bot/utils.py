import logging
import mimetypes
from asgiref.sync import sync_to_async

from aiogram.types import Message, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import Bloger, Message as DBMessage

async def send_message(message: Message, bloger: Bloger):
    try:
        msg = await sync_to_async(DBMessage.objects.first)()
        keyboard = await get_keyboard(msg.button_text, bloger.ref_link_to_site)

        if msg.media:
            mime, _ = mimetypes.guess_type(msg.media.path)
            file = FSInputFile(msg.media.path)

            if "image" in mime:
                await message.answer_photo(
                    photo=file,
                    caption=msg.text,
                    reply_markup=keyboard
                )
            elif "video" in mime:
                await message.answer_video(
                    video=file,
                    caption=msg.text,
                    reply_markup=keyboard
                )
            else:
                await message.answer_document(
                    document=file,
                    caption=msg.text,
                    reply_markup=keyboard
                )
        else:
            await message.answer(
                text=msg.text,
                reply_markup=keyboard
            )

    except Exception as e:
        logging.error(f"Error sending message: {e}")

async def get_keyboard(text: str, link: str):
    kb = InlineKeyboardBuilder()

    kb.button(text=text, url=link)

    return kb.as_markup()
    