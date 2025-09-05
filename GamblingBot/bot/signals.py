import asyncio
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import Bloger, Bot
from .bot_instance import setup_and_start

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Bloger)
def generate_ref_link(sender, instance, created, **kwargs):
    if created and not instance.ref_link_to_bot:
        bot_username = instance.bot.username    
        instance.ref_link_to_bot = f'https://t.me/{bot_username}?start=ref_{instance.id}'
        instance.save(update_fields=["ref_link_to_bot"])

@receiver(post_save, sender=Bot)
def start_new_bot(sender, instance, created, **kwargs):
    if not created:
        return

    logger.info(f'Створено нового бота {instance.id}')

    def run_bot():
        asyncio.run(setup_and_start(instance))

    import threading
    transaction.on_commit(lambda: threading.Thread(target=run_bot).start())