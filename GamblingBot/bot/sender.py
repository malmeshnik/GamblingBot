import asyncio
import mimetypes
import logging
from datetime import datetime
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

# Налаштування логера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')
if not logger.handlers:
    file_handler = logging.FileHandler('bot_sender.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

def get_keyboard(button_text: str, url: str):
    logger.debug(f"🔘 Створення клавіатури з текстом: {button_text} та URL: {url}")
    kb = InlineKeyboardBuilder()
    kb.button(text=button_text, url=url)
    return kb.as_markup()

async def send_message_safe(bot: Bot, user, msg_text, keyboard=None, media_file=None, mime=None, send_button=True):
    """
    Очікує aiogram.Bot екземпляр в `bot`.
    Повертає aiogram Message при успіху або False при помилці.
    """
    logger.info(f"📤 Початок відправки повідомлення користувачу {user.telegram_id}")
    start_time = datetime.now()

    if not send_button:
        keyboard = None
        logger.debug("🔘 Кнопки відключені для цього повідомлення")

    try:
        if media_file:
            logger.debug(f"📎 Відправка медіа типу {mime} для {user.telegram_id}")
            if mime and "image" in mime:
                sent = await bot.send_photo(int(user.telegram_id), media_file, caption=msg_text, reply_markup=keyboard, parse_mode="HTML")
            elif mime and "video" in mime:
                sent = await bot.send_video(int(user.telegram_id), media_file, caption=msg_text, reply_markup=keyboard, parse_mode="HTML")
            else:
                sent = await bot.send_document(int(user.telegram_id), media_file, caption=msg_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            logger.debug("💬 Відправка текстового повідомлення")
            sent = await bot.send_message(int(user.telegram_id), msg_text, reply_markup=keyboard, parse_mode="HTML")

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ Повідомлення успішно надіслано користувачу {user.telegram_id} за {duration:.2f} сек")
        user.status = UserStatus.ACTIVE
        await sync_to_async(user.save)(update_fields=["status"])
        return sent

    except TelegramForbiddenError as e:
        txt = str(e).lower()
        if "blocked" in txt:
            user.status = UserStatus.BLOCKED
            logger.warning(f"🚫 Користувач {user.telegram_id} заблокував бота")
        else:
            user.status = UserStatus.FORBIDDEN
            logger.warning(f"⛔ Доступ заборонено для користувача {user.telegram_id}: {e}")
        await sync_to_async(user.save)(update_fields=["status"])
        return False

    except TelegramBadRequest as e:
        txt = str(e).lower()
        if "deactivated" in txt or "chat not found" in txt:
            user.status = UserStatus.DELETED
            logger.warning(f"❌ Аккаунт/чат {user.telegram_id} недоступний: {e}")
        else:
            user.status = UserStatus.FORBIDDEN
            logger.warning(f"🚫 Помилка запиту для {user.telegram_id}: {e}")
        await sync_to_async(user.save)(update_fields=["status"])
        return False

    except TelegramRetryAfter as e:
        wait = e.retry_after
        logger.warning(f"⏳ Flood control для {user.telegram_id}, очікування {wait} сек")
        await asyncio.sleep(wait)
        logger.info(f"🔄 Повторна спроба надсилання для {user.telegram_id}")
        return await send_message_safe(bot, user, msg_text, keyboard, media_file, mime, send_button)

    except Exception as e:
        logger.error(f"❌ Невідома помилка при відправці {user.telegram_id}: {e}", exc_info=True)
        user.status = UserStatus.FORBIDDEN
        await sync_to_async(user.save)(update_fields=["status"])
        return False

async def send_messages_after_start():
    start_time = datetime.now()
    logger.info("🔄 Початок відправки повідомлень після старту")

    messages = await sync_to_async(list)(
        ScheduledMessage.objects.filter(
            send_at__lte=timezone.now(),
            sent=False
        ).select_for_update()
    )

    logger.info(f"📨 Знайдено {len(messages)} повідомлень для відправки після старту")

    for msg in messages:
        msg_start = datetime.now()
        logger.info(f"📝 Обробка повідомлення ID: {msg.id}")

        media_file = FSInputFile(msg.media.path) if msg.media else None
        mime, _ = mimetypes.guess_type(msg.media.path) if msg.media else (None, None)

        user = await sync_to_async(lambda: msg.user)()
        bloger = await sync_to_async(lambda: user.bloger)()
        bot_obj = await sync_to_async(lambda: msg.bot)()
        if not bot_obj:
            logger.warning(f"⚠️ Бот не знайдено для msg {msg.id}")
            continue

        async with Bot(bot_obj.token) as bot_instance:
            keyboard = get_keyboard(msg.button_text, bloger.ref_link_to_site) if bloger else None
            sent_msg = await send_message_safe(bot_instance, user, msg.text, keyboard, media_file, mime)

        if sent_msg:
            # видаляємо/позначаємо після успіху
            await sync_to_async(msg.delete)()
            logger.debug(f"🗑 Видалено повідомлення ID: {msg.id} після успішної відправки")
        else:
            logger.warning(f"⚠️ Повідомлення ID {msg.id} не було відправлено; залишено в базі")

        msg_duration = (datetime.now() - msg_start).total_seconds()
        logger.info(f"⏱ Повідомлення {msg.id} оброблено за {msg_duration:.2f} сек")

    total_duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"🏁 Завершено відправку повідомлень після старту. Час: {total_duration:.2f} сек")

async def send_scheduled_messages():
    start_time = datetime.now()
    logger.info("🔄 Початок відправки запланованих повідомлень")

    messages = await sync_to_async(list)(
        ScheduledMessage.objects.filter(send_at__lte=timezone.now(), sent=False)
    )

    logger.info(f"📨 Знайдено {len(messages)} запланованих повідомлень")

    semaphore = asyncio.Semaphore(10)
    logger.debug(f"🔓 Встановлено семафор з лімітом: 10")

    async def send_with_limit(user, bot_instance, msg, media_file, mime):
        async with semaphore:
            start = datetime.now()
            logger.debug(f"👤 Відправка користувачу {user.telegram_id}")

            bloger = user.bloger
            if not bloger:
                logger.warning(f"⚠️ Пропуск користувача {user.telegram_id} - блогер не знайдений")
                return False

            button_link = msg.button_link or bloger.ref_link_to_site
            keyboard = get_keyboard(msg.button_text, button_link)
            message_text = msg.text.format(name=user.first_name) if "{name}" in msg.text else msg.text

            try:
                sent = await send_message_safe(bot_instance, user, message_text, keyboard, media_file, mime, msg.send_button)
                duration = (datetime.now() - start).total_seconds()
                if sent:
                    logger.debug(f"✅ Відправлено користувачу {user.telegram_id} за {duration:.2f} сек")
                else:
                    logger.debug(f"❌ Не вдалось відправити користувачу {user.telegram_id}")
                await asyncio.sleep(0.2)
                return bool(sent)
            except Exception as ex:
                logger.error(f"❌ Помилка відправки користувачу {user.telegram_id}: {ex}", exc_info=True)
                return False

    for msg in messages:
        msg_start = datetime.now()
        logger.info(f"📝 Обробка повідомлення ID: {msg.id}")

        # Позначати як 'in progress' або видаляти після успіху — тут ставимо sent=True перед відправкою, але можна змінити на після успіху
        msg.sent = True
        await sync_to_async(msg.save)()
        logger.debug(f"💾 Повідомлення {msg.id} позначено як відправлене")

        if await sync_to_async(lambda: msg.folder_id)():
            bots_list = await sync_to_async(lambda: list(msg.folder.bots.all()))()
            logger.info(f"🤖 Відправка через {len(bots_list)} ботів з папки")
        else:
            bots_list = [await sync_to_async(lambda: msg.bot)()]
            logger.info("🤖 Відправка через один бот")

        for bot_obj in bots_list:
            if not bot_obj:
                logger.warning("⚠️ Пропуск: bot_obj is None")
                continue

            async with Bot(bot_obj.token) as bot_instance:
                logger.info(f"🤖 Обробка бота: {bot_obj.username}")

                users = await sync_to_async(list)(
                    User.objects.select_related("bloger").filter(bot=bot_obj).distinct()
                )

                logger.info(f"👥 Знайдено {len(users)} користувачів для бота {bot_obj.username}")

                media_file = FSInputFile(msg.media.path) if msg.media else None
                mime, _ = mimetypes.guess_type(msg.media.path) if msg.media else (None, None)

                tasks = [send_with_limit(user, bot_instance, msg, media_file, mime) for user in users]
                chunks = [tasks[i : i + 5] for i in range(0, len(tasks), 5)]

                logger.info(f"📦 Розділено на {len(chunks)} частин по 5 повідомлень")

                for i, chunk in enumerate(chunks, 1):
                    chunk_start = datetime.now()
                    logger.info(f"📤 Відправка частини {i}/{len(chunks)} ({len(chunk)} повідомлень)")

                    results = await asyncio.gather(*chunk, return_exceptions=True)

                    successful = len([r for r in results if r is True])
                    failed = len([r for r in results if r is False or isinstance(r, Exception)])

                    chunk_duration = (datetime.now() - chunk_start).total_seconds()
                    logger.info(f"📊 Частина {i}: ✅ Успішно: {successful}, ❌ Помилок: {failed}, ⏱ Час: {chunk_duration:.2f} сек")

                    await asyncio.sleep(1)

                bot_duration = (datetime.now() - msg_start).total_seconds()
                logger.info(f"⏱ Час роботи з ботом {bot_obj.username}: {bot_duration:.2f} сек")

        msg_duration = (datetime.now() - msg_start).total_seconds()
        logger.info(f"⏱ Час обробки повідомлення ID {msg.id}: {msg_duration:.2f} сек")

    total_duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"🏁 Розсилку завершено. Загальний час: {total_duration:.2f} сек")