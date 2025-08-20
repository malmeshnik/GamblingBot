from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import Bloger

@receiver(post_save, sender=Bloger)
def generate_ref_link(sender, instance, created, **kwargs):
    if created and not instance.ref_link_to_bot:
        bot_username = getattr(settings, 'BOT_USERNAME')    
        instance.ref_link_to_bot = f'https://t.me/{bot_username}?start=ref_{instance.id}'
        instance.save(update_fields=["ref_link_to_bot"])