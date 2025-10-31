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

file_handler = logging.FileHandler('bot_sender.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

def get_keyboard(button_text: str, url: str):
    logger.debug(f"🔘 Створення клавіатури з текстом: {button_text} та URL: {url}")
    kb = InlineKeyboardBuilder()
    kb.button(text=button_text, url=url)
    return kb.as_markup()

async def send_message_safe(bot: Bot, user, msg_text, keyboard=None, media_file=None, mime=None, send_button=True):
    logger.info(f"📤 Початок відправки повідомлення користувачу {user.telegram_id}")
    start_time = datetime.now()
    
    if not send_button:
            keyboard = None
            logger.debug("🔘 Кнопки вимкнені для цього повідомлення")
        
    try:
        if media_file:
            logger.info(f"📎 Відправка медіафайлу типу: {mime}")
            if mime and "image" in mime:
                logger.debug("🖼 Відправка зображення")
                msg = await bot.send_photo(
                    int(user.telegram_id),
                    media_file,
                    caption=msg_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            elif mime and "video" in mime:
                logger.debug("🎥 Відправка відео")
                msg = await bot.send_video(
                    int(user.telegram_id),
                    media_file,
                    caption=msg_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            else:
                logger.debug("📄 Відправка документа")
                msg = await bot.send_document(
                    int(user.telegram_id),
                    media_file,
                    caption=msg_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        else:
            logger.debug("💬 Відправка текстового повідомлення")
            msg = await bot.send_message(
                int(user.telegram_id),
                msg_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"✅ Повідомлення успішно надіслано користувачу {user.telegram_id} за {duration:.2f} сек")
        
        user.status = UserStatus.ACTIVE
        return msg

    except TelegramForbiddenError as e:
        msg = str(e).lower()
        if "blocked" in msg:
            user.status = UserStatus.BLOCKED
            logger.error(f"🚫 Користувач {user.telegram_id} заблокував бота")
        else:
            user.status = UserStatus.FORBIDDEN
            logger.error(f"⛔ Доступ заборонено для користувача {user.telegram_id}")
        logger.warning(f"⚠️ TelegramForbiddenError: {user.telegram_id} Помилка: {e}")
        
    except TelegramBadRequest as e:
        msg = str(e).lower()
        if "deactivated" in msg:
            user.status = UserStatus.DELETED
            logger.error(f"❌ Акаунт користувача {user.telegram_id} деактивовано")
        elif "chat not found" in msg:
            user.status = UserStatus.DELETED
            logger.error(f"❌ Чат з користувачем {user.telegram_id} не знайдено")
        else:
            user.status = UserStatus.FORBIDDEN
            logger.error(f"⛔ Помилка запиту для користувача {user.telegram_id}")
        logger.warning(f"🚫 TelegramBadRequest: {user.telegram_id} Помилка: {e}")
        
    except TelegramRetryAfter as e:
        retry_time = e.retry_after
        logger.warning(f"⏳ Flood control для {user.telegram_id}, очікування {retry_time} сек")
        await asyncio.sleep(retry_time)
        logger.info(f"🔄 Повторна спроба відправки для {user.telegram_id}")
        return await send_message_safe(
            bot, user, msg_text, keyboard, media_file, mime
        )
        
    except Exception as e:
        logger.error(f"❌ Невідома помилка при відправці {user.telegram_id}: {e}", exc_info=True)
        
    finally:
        logger.debug(f"💾 Збереження статусу користувача {user.telegram_id}: {user.status}")
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
        
        await sync_to_async(msg.delete)()
        logger.debug(f"🗑 Видалено повідомлення ID: {msg.id}")
        
        media_file = FSInputFile(msg.media.path) if msg.media else None
        mime, _ = mimetypes.guess_type(msg.media.path) if msg.media else (None, None)
        
        if media_file:
            logger.info(f"📎 Медіафайл: {mime}")

        user = await sync_to_async(lambda: msg.user)()
        bloger = await sync_to_async(lambda: user.bloger)()
        bot = await sync_to_async(lambda: msg.bot)()
        bot_token = bot.token

        if not bloger:
            logger.warning(f"⚠️ Пропуск повідомлення ID {msg.id} - блогер не знайдений")
            continue

        async with Bot(bot_token) as bot_instance:
            keyboard = get_keyboard(msg.button_text, bloger.ref_link_to_site) if bloger else None
            await send_message_safe(bot_instance, user, msg.text, keyboard, media_file, mime)

        msg_duration = (datetime.now() - msg_start).total_seconds()
        logger.info(f"✅ Повідомлення {msg.id} відправлено користувачу {user.telegram_id} за {msg_duration:.2f} сек")

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

    async def send_with_limit(user, bot, msg, media_file, mime):
        async with semaphore:
            start = datetime.now()
            logger.debug(f"👤 Відправка користувачу {user.telegram_id}")
            
            bloger = user.bloger
            if not bloger:
                logger.warning(f"⚠️ Пропуск користувача {user.telegram_id} - блогер не знайдений")
                return

            button_link = msg.button_link or bloger.ref_link_to_site
            keyboard = get_keyboard(msg.button_text, button_link)
            message_text = msg.text.format(name=user.first_name) if "{name}" in msg.text else msg.text
            
            try:
                await send_message_safe(
                    bot,
                    user,
                    message_text,
                    keyboard,
                    media_file,
                    mime,
                    msg.send_button,
                )
                duration = (datetime.now() - start).total_seconds()
                logger.debug(f"✅ Відправлено користувачу {user.telegram_id} за {duration:.2f} сек")
                await asyncio.sleep(0.2)
                
            except TelegramRetryAfter as e:
                logger.warning(f"⏳ Flood limit для {user.telegram_id}, очікування {e.retry_after} сек")
                await asyncio.sleep(e.retry_after)
                await send_message_safe(
                    bot,
                    user,
                    message_text,
                    keyboard,
                    media_file,
                    mime,
                    msg.send_button,
                )
                
            except Exception as ex:
                logger.error(f"❌ Помилка відправки користувачу {user.telegram_id}: {ex}", exc_info=True)

    for msg in messages:
        msg_start = datetime.now()
        logger.info(f"📝 Обробка повідомлення ID: {msg.id}")
        
        msg.sent = True
        await sync_to_async(msg.save)()
        logger.debug(f"💾 Повідомлення {msg.id} позначено як відправлене")

        if await sync_to_async(lambda: msg.folder_id)():
            bots = await sync_to_async(lambda: list(msg.folder.bots.all()))()
            logger.info(f"🤖 Відправка через {len(bots)} ботів з папки")
        else:
            bots = [await sync_to_async(lambda: msg.bot)()]
            logger.info("🤖 Відправка через один бот")

        for bot in bots:

            async with Bot(bot.token) as bot_instance:
                bot_start = datetime.now()
                logger.info(f"🤖 Обробка бота: {bot.username}")
                
                users = await sync_to_async(list)(
                    User.objects.select_related("bloger")
                    .filter(bot=bot)
                    .distinct()
                )
                
                logger.info(f"👥 Знайдено {len(users)} користувачів для бота {bot.username}")
                
                media_file = FSInputFile(msg.media.path) if msg.media else None
                mime, _ = mimetypes.guess_type(msg.media.path) if msg.media else (None, None)
                
                if media_file:
                    logger.info(f"📎 Тип медіафайлу: {mime}")

                tasks = [send_with_limit(user, bot_instance, msg, media_file, mime) for user in users]
                chunks = [tasks[i : i + 5] for i in range(0, len(tasks), 5)]
                
                logger.info(f"📦 Розділено на {len(chunks)} частин по 5 повідомлень")

                for i, chunk in enumerate(chunks, 1):
                    chunk_start = datetime.now()
                    logger.info(f"📤 Відправка частини {i}/{len(chunks)} ({len(chunk)} повідомлень)")
                    
                    results = await asyncio.gather(*chunk, return_exceptions=True)
                    
                    successful = len([r for r in results if r and not isinstance(r, Exception)])
                    failed = len([r for r in results if isinstance(r, Exception)])
                    
                    chunk_duration = (datetime.now() - chunk_start).total_seconds()
                    logger.info(f"📊 Частина {i}: ✅ Успішно: {successful}, ❌ Помилок: {failed}, ⏱ Час: {chunk_duration:.2f} сек")
                    
                    await asyncio.sleep(1)
                
                bot_duration = (datetime.now() - bot_start).total_seconds()
                logger.info(f"⏱ Час роботи з ботом {bot.username}: {bot_duration:.2f} сек")

        msg_duration = (datetime.now() - msg_start).total_seconds()
        logger.info(f"⏱ Час обробки повідомлення ID {msg.id}: {msg_duration:.2f} сек")

    total_duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"🏁 Розсилку завершено. Загальний час: {total_duration:.2f} сек")