import asyncio
import mimetypes
import logging
from asgiref.sync import sync_to_async
from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramRetryAfter,
)
from django.utils import timezone
from .models import User, ScheduledMessage, MessageAfterStart, UserStatus

logger = logging.getLogger(__name__)


def get_keyboard(button_text: str, url: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=button_text, url=url)
    return kb.as_markup()


async def send_message_safe(
    bot_token: str,
    user,
    msg_text,
    keyboard=None,
    media_file=None,
    mime=None,
    send_button=True,
):
    async with Bot(bot_token) as bot:
        if not send_button:
            keyboard = None
            
        try:
            if media_file:
                if mime and "image" in mime:
                    msg = await bot.send_photo(
                        int(user.telegram_id),
                        media_file,
                        caption=msg_text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
                elif mime and "video" in mime:
                    msg = await bot.send_video(
                        int(user.telegram_id),
                        media_file,
                        caption=msg_text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
                else:
                    msg = await bot.send_document(
                        int(user.telegram_id),
                        media_file,
                        caption=msg_text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
            else:
                msg = await bot.send_message(
                    int(user.telegram_id),
                    msg_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )

            logger.info(f"✅ Повідомлення надіслано користувачу {user.telegram_id}")
            user.status = UserStatus.ACTIVE
            return msg

        except TelegramForbiddenError as e:
            msg = str(e).lower()
            if "blocked" in msg:
                user.status = UserStatus.BLOCKED
            else:
                user.status = UserStatus.FORBIDDEN
            logger.warning(f"⚠️ Невірний telegram_id: {user.telegram_id} Помилка: {e}")
        except TelegramBadRequest as e:
            msg = str(e).lower()
            if "deactivated" in msg:
                user.status = UserStatus.DELETED
            elif "chat not found" in msg:
                user.status = UserStatus.DELETED
            else:
                user.status = UserStatus.FORBIDDEN
            logger.warning(f"🚫 Користувач {user.telegram_id} заблокував бота {e}")
        except TelegramRetryAfter as e:
            logger.warning(
                f"⏳ Flood control для {user.telegram_id}, чекаємо {e.retry_after} сек..."
            )
            await asyncio.sleep(e.retry_after)
            return await send_message_safe(
                bot_token, user, msg_text, keyboard, media_file, mime
            )
        except Exception as e:
            logger.error(
                f"❌ Помилка при надсиланні користувачу {user.telegram_id}: {e}"
            )
        finally:
            await sync_to_async(user.save)(update_fields=["status"])

        return False


async def send_messages_after_start():
    messages = await sync_to_async(list)(
        MessageAfterStart.objects.filter(send_at__lte=timezone.now(), sent=False)
    )

    for msg in messages:
        await sync_to_async(msg.delete)()
        media_file = FSInputFile(msg.media.path) if msg.media else None
        mime, _ = mimetypes.guess_type(msg.media.path) if msg.media else (None, None)

        user = await sync_to_async(lambda: msg.user)()
        bloger = await sync_to_async(lambda: user.bloger)()
        bot = await sync_to_async(lambda: msg.bot)()
        bot_token = bot.token
        if not bloger:
            continue

        keyboard = get_keyboard(msg.button_text, bloger.ref_link_to_site)
        await send_message_safe(bot_token, user, msg.text, keyboard, media_file, mime)

        logger.info(
            f"📨 Заплановане повідомлення {msg.id} розіслано користувачу {user.telegram_id}"
        )


async def send_scheduled_messages():
    messages = await sync_to_async(list)(
        ScheduledMessage.objects.filter(send_at__lte=timezone.now(), sent=False)
    )

    semaphore = asyncio.Semaphore(10)

    async def send_with_limit(user, bot, msg, media_file, mime):
        bloger = user.bloger
        if not bloger:
            return

        button_link = msg.button_link or bloger.ref_link_to_site
        keyboard = get_keyboard(msg.button_text, button_link)
        message_text = (
            msg.text.format(name=user.first_name) if "{name}" in msg.text else msg.text
        )
        bot_token = bot.token

        async with semaphore:
            try:
                await send_message_safe(
                    bot_token,
                    user,
                    message_text,
                    keyboard,
                    media_file,
                    mime,
                    msg.send_button,
                )
                await asyncio.sleep(0.2)
            except TelegramRetryAfter as e:
                logger.warning(
                    f"⏱ TelegramRetryAfter для {user.telegram_id}, чекаємо {e.retry_after}s"
                )
                await asyncio.sleep(e.retry_after)
                await send_message_safe(
                    bot_token,
                    user,
                    message_text,
                    keyboard,
                    media_file,
                    mime,
                    msg.send_button,
                )
            except Exception as ex:
                logger.error(
                    f"❌ Помилка при надсиланні користувачу {user.telegram_id}: {ex}"
                )

    for msg in messages:
        msg.sent = True
        if await sync_to_async(lambda: msg.folder_id)():
            bots = await sync_to_async(lambda: list(msg.folder.bots.all()))()
        else:
            bots = [await sync_to_async(lambda: msg.bot)()]

        for bot in bots:
            users = await sync_to_async(list)(
                User.objects.select_related("bloger").filter(bot=bot)
            )
            await sync_to_async(msg.save)()
            media_file = FSInputFile(msg.media.path) if msg.media else None
            mime, _ = mimetypes.guess_type(msg.media.path) if msg.media else (None, None)

            tasks = [send_with_limit(user, bot, msg, media_file, mime) for user in users]

            for chunk in [tasks[i : i + 5] for i in range(0, len(tasks), 5)]:
                await asyncio.gather(*chunk, return_exceptions=True)
                await asyncio.sleep(1)