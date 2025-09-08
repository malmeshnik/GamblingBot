import asyncio
import logging

from aiogram import Bot as AioBot
from aiogram.types import MenuButtonWebApp, WebAppInfo, MenuButtonDefault

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import Bloger, Bot
from .bot_instance import setup_and_start

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
console_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(console_handler)

@receiver(post_save, sender=Bloger)
def generate_ref_link(sender, instance, created, **kwargs):
    if created and not instance.ref_link_to_bot:
        bot_username = instance.bot.username    
        instance.ref_link_to_bot = f'https://t.me/{bot_username}?start=ref_{instance.id}'
        instance.save(update_fields=["ref_link_to_bot"])

# @receiver(post_save, sender=Bot)
# def start_new_bot(sender, instance, created, **kwargs):
#     if not created:
#         return

#     logger.info(f'Створено нового бота {instance.id}')

#     def run_bot():
#         asyncio.run(setup_and_start(instance))

#     import threading
#     transaction.on_commit(lambda: threading.Thread(target=run_bot).start())

# @receiver(post_save, sender=Bot)
# def update_bot_menu(sender, instance: Bot, **kwargs):
#     if not instance.token:
#         return

#     async def set_menu():
#         bot = AioBot(token=instance.token)
#         try:
#             if instance.button_text and instance.miniapp_link:
#                 await bot.set_chat_menu_button(
#                     menu_button=MenuButtonWebApp(
#                         text=instance.button_text,
#                         web_app=WebAppInfo(url=instance.miniapp_link)
#                     )
#                 )

#                 logger.info(f'Меню змінено для ботa {instance.username}')
#             else:
#                 await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
#         finally:
#             await bot.session.close()

#     asyncio.run(set_menu())