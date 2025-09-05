import asyncio
import logging
from urllib.parse import parse_qs

from django.contrib import admin, messages

from .models import *
from .utils import check_bot

class BotRelatedAdmin(admin.ModelAdmin):
    exclude = ('bot',)

    def get_list_display(self, request):
        if self.model.__name__ == 'User':
            return ('telegram_id', 'username', 'bloger')
        elif self.model.__name__ == 'Message':
            return ('text', 'button_text')
        elif self.model.__name__ == 'ScheduledMessage':
            return('text', 'button_text', 'send_at', 'sent')
        elif self.model.__name__ == 'Campain':
            return ('text', 'button_text', 'delay_minutes')

        return super().get_list_display(request)
    
    def save_model(self, request, obj, form, change):
        if hasattr(obj, 'bot_id'):
            if not obj.bot_id:
                bot_id = None

                if request.GET.get('bot__id__exact'):
                    bot_id = request.GET['bot__id__exact']

                elif request.GET.get('_changelist_filters'):
                    filters = parse_qs(request.GET['_changelist_filters'])

                    if 'bot__id__exact' in filters:
                        bot_id = filters['bot__id__exact'][0]
                        
                if bot_id:
                    obj.bot_id = bot_id

        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        bot_id = request.GET.get('bot__id__exact')
        if bot_id:
            return qs.filter(bot_id=bot_id)
        return qs

class MyAdminSite(admin.AdminSite):
    site_header = "Управління гемблінговими ботами"

    def get_app_list(self, request):
        bots = Bot.objects.all()
        app_list = []
        for bot in bots:
            app_list.append({
                'name': bot.name,
                'app_label': f'bot_{bot.id}',
                'bot_id': bot.id,
                'models': [
                    {'name': 'Користувачі', 'admin_url': f'/admin/bot/user/?bot__id__exact={bot.id}'},
                    {'name': 'Повідомлення', 'admin_url': f'/admin/bot/message/?bot__id__exact={bot.id}'},
                    {'name': 'Блогери', 'admin_url': f'/admin/bot/bloger/?bot__id__exact={bot.id}'},
                    {'name': 'Заплановані повідомлення', 'admin_url': f'/admin/bot/scheduledmessage/?bot__id__exact={bot.id}'},
                    {'name': 'Повідомлення після старту', 'admin_url': f'/admin/bot/campain/?bot__id__exact={bot.id}'},
                ]
            })
        return app_list
    
class BotAdmin(BotRelatedAdmin):
    def save_model(self, request, obj, form, change):
        try:
            bot_info = asyncio.run(check_bot(obj.token))
            obj.bot_id = bot_info.id
            obj.username = bot_info.username
            logging.info(f'Bot username {bot_info.username}')

            self.message_user(request, f'Bot перевірено успішно: {bot_info.username}', level=messages.SUCCESS)
            
            super().save_model(request, obj, form, change)

        except Exception as e:
            logging.error(f'Помилка при перевірці бота: {e}')
            self.message_user(request, f'Помилка при перевірці бота: {e}', level=messages.ERROR)
            
            form.add_error('token', f'Помилка при перевірці токена: {e}')

class BlogerAdmin(BotRelatedAdmin):
    list_display = ('name', 'invited_people', 'ref_link_to_site', 'ref_link_to_bot')
    list_editable = ('ref_link_to_site',)

admin_site = MyAdminSite(name='myadmin')

admin_site.register(User, BotRelatedAdmin)
admin_site.register(Message, BotRelatedAdmin)
admin_site.register(Bloger, BlogerAdmin)
admin_site.register(ScheduledMessage, BotRelatedAdmin)
admin_site.register(Campain, BotRelatedAdmin)
admin_site.register(Bot, BotAdmin)