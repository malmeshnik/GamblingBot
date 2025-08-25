import asyncio
import mimetypes
import logging
from asgiref.sync import sync_to_async
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramRetryAfter,
)
from django.utils import timezone
from .models import User, ScheduledMessage, MessageAfterStart
from .bot_instance import bot

logger = logging.getLogger(__name__)


def get_keyboard(button_text: str, url: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=button_text, url=url)
    return kb.as_markup()


async def send_message_safe(user, msg_text, keyboard=None, media_file=None, mime=None):
    try:
        if media_file:
            if mime and "image" in mime:
                await bot.send_photo(
                    int(user.telegram_id),
                    media_file,
                    caption=msg_text,
                    reply_markup=keyboard,
                )
            elif mime and "video" in mime:
                await bot.send_video(
                    int(user.telegram_id),
                    media_file,
                    caption=msg_text,
                    reply_markup=keyboard,
                )
            else:
                await bot.send_document(
                    int(user.telegram_id),
                    media_file,
                    caption=msg_text,
                    reply_markup=keyboard,
                )
        else:
            await bot.send_message(int(user.telegram_id), msg_text, reply_markup=keyboard)

        logger.info(f"✅ Повідомлення надіслано користувачу {user.telegram_id}")
        return True

    except TelegramForbiddenError:
        logger.warning(f"🚫 Користувач {user.telegram_id} заблокував бота")
    except TelegramBadRequest:
        logger.warning(f"⚠️ Невірний telegram_id: {user.telegram_id}")
    except TelegramRetryAfter as e:
        logger.warning(
            f"⏳ Flood control для {user.telegram_id}, чекаємо {e.retry_after} сек..."
        )
        await asyncio.sleep(e.retry_after)
        return await send_message_safe(user, msg_text, keyboard, media_file, mime)
    except Exception as e:
        logger.error(f"❌ Помилка при надсиланні користувачу {user.telegram_id}: {e}")
    return False


async def send_messages_after_start():
    messages = await sync_to_async(list)(
        MessageAfterStart.objects.filter(send_at__lte=timezone.now(), sent=False)
    )

    for msg in messages:
        media_file = FSInputFile(msg.media.path) if msg.media else None
        mime, _ = mimetypes.guess_type(msg.media.path) if msg.media else (None, None)

        user = await sync_to_async(lambda: msg.user)()
        bloger = await sync_to_async(lambda: user.bloger)()
        if not bloger:
            continue

        keyboard = get_keyboard(msg.button_text, bloger.ref_link_to_site)
        await send_message_safe(user, msg.text, keyboard, media_file, mime)

        await sync_to_async(msg.delete)()
        logger.info(
            f"📨 Заплановане повідомлення {msg.id} розіслано користувачу {user.telegram_id}"
        )


async def send_scheduled_messages():
    messages = await sync_to_async(list)(
        ScheduledMessage.objects.filter(send_at__lte=timezone.now(), sent=False)
    )
    users = await sync_to_async(
        lambda: list(User.objects.select_related("bloger").all())
    )()

    semaphore = asyncio.Semaphore(10)  # максимум 10 одночасних відправлень

    async def send_with_limit(user, msg, media_file, mime):
        bloger = user.bloger
        if not bloger:
            return

        button_link = msg.button_link or bloger.ref_link_to_site
        keyboard = get_keyboard(msg.button_text, button_link)
        message_text = msg.text.format(name=user.first_name) if "{name}" in msg.text else msg.text

        async with semaphore:
            try:
                await send_message_safe(user, message_text, keyboard, media_file, mime)
                await asyncio.sleep(0.2)  # невелика пауза між повідомленнями
            except TelegramRetryAfter as e:
                logger.warning(f"⏱ TelegramRetryAfter для {user.telegram_id}, чекаємо {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
                await send_message_safe(user, message_text, keyboard, media_file, mime)
            except Exception as ex:
                logger.error(f"❌ Помилка при надсиланні користувачу {user.telegram_id}: {ex}")

    for msg in messages:
        msg.sent = True
        await sync_to_async(msg.save)()
        media_file = FSInputFile(msg.media.path) if msg.media else None
        mime, _ = mimetypes.guess_type(msg.media.path) if msg.media else (None, None)

        tasks = [send_with_limit(user, msg, media_file, mime) for user in users]

        # Виконуємо у чанках по 5
        for chunk in [tasks[i : i + 5] for i in range(0, len(tasks), 5)]:
            await asyncio.gather(*chunk, return_exceptions=True)
            await asyncio.sleep(1)  # пауза між чанками

        logger.info(f"📨 Заплановане повідомлення {msg.id} розіслано всім користувачам")