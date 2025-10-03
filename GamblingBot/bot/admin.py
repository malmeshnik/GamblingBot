import asyncio
import logging
from urllib.parse import parse_qs

from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

from .models import *
from .utils import check_bot

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
console_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(console_handler)


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

        if hasattr(obj, 'folder_id'):
            if not obj.folder_id:
                folder_id = None

                if request.GET.get('folder__id__exact'):
                    folder_id = request.GET['folder__id__exact']

                elif request.GET.get('_changelist_filters'):
                    filters = parse_qs(request.GET['_changelist_filters'])

                    if 'folder__id__exact' in filters:
                        folder_id = filters['folder__id__exact'][0]
                        
                if folder_id:
                    obj.folder_id = folder_id

        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        bot_id = request.GET.get('bot__id__exact')
        folder_id = request.GET.get('folder__id__exact')
        if bot_id:
            return qs.filter(bot_id=bot_id)
        elif folder_id: 
            return qs.filter(folder_id=folder_id)
        return qs

class MyAdminSite(admin.AdminSite):
    site_header = "Управління гемблінговими ботами"

    def get_app_list(self, request):
        folders = Folder.objects.prefetch_related("bots")
        app_list = []

        for folder in folders:
            folder_dict = {
                "name": folder.name,
                "id": f"folder_{folder.id}",
                "bots": [],
                "folder_id": folder.id
            }

            for bot in folder.bots.all():
                folder_dict["bots"].append({
                    "name": bot.name,
                    "app_label": f"bot_{bot.id}",
                    "bot_id": bot.id,
                    "models": [
                        {"name": "Користувачі", "admin_url": f"/admin/bot/user/?bot__id__exact={bot.id}"},
                        {"name": "Повідомлення", "admin_url": f"/admin/bot/message/?bot__id__exact={bot.id}"},
                        {"name": "Блогери", "admin_url": f"/admin/bot/bloger/?bot__id__exact={bot.id}"},
                        {"name": "Заплановані повідомлення", "admin_url": f"/admin/bot/scheduledmessage/?bot__id__exact={bot.id}"},
                        {"name": "Повідомлення після старту", "admin_url": f"/admin/bot/campain/?bot__id__exact={bot.id}"},
                        {"name": "Статистика", "admin_url": f"/admin/bot/botstatistics/?bot__id__exact={bot.id}"},
                    ]
                })
            app_list.append(folder_dict)

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

class FolderAdmin(BotRelatedAdmin):
    list_display = ('name', )

class BotStatisticsAdmin(BotRelatedAdmin):
    change_list_template = "admin/statistics.html"

    def changelist_view(self, request: HttpRequest, extra_context=None):
        bot_id = request.GET.get('bot__id__exact')

        context = self.admin_site.each_context(request)
        logger.info(f'Bot ID {bot_id}')

        if bot_id:
            active_percent = 0
            users = User.objects.filter(bot_id=bot_id)
            bot = Bot.objects.filter(id=bot_id).first()
            logger.info(f'Users count for bot {bot.name}: {len(users)}')
            title = f'📊 Статистика по боту "{bot.name}"'

            stats = users.values('status').annotate(count=models.Count('status'))

            stat_dict = {s['status']: s['count'] for s in stats}   
            total = sum(stat_dict.values())
            logger.info(f'Bot stats: {stats}')

            # відсоток активних користувачів
            active_count = stat_dict.get("active", 0)
            if total > 0:
                active_percent = round((active_count / total) * 100, 2)

            context.update({
                'bot_stats': stat_dict,
                'bot': bot,
                'active_percent': active_percent,
                'stat_title': title
            })

        else:
            title = f'📊 Статистика всіх ботів'
            users = User.objects.all()

            stats = users.values('status').annotate(count=models.Count('status'))
            stat_dict = {s['status']: s['count'] for s in stats}
            total = sum(stat_dict.values())

            if total > 0:
                active_percent = round((stat_dict.get('active', 0) / total) * 100, 2)

            context.update({
                'bot_stats': stat_dict,
                'active_percent': active_percent,
                'stat_title': title
            })

        return TemplateResponse(
            request,
            self.change_list_template,
            context,
        )
        

admin_site = MyAdminSite(name='myadmin')

admin_site.register(BotStatistics, BotStatisticsAdmin)
admin_site.register(User, BotRelatedAdmin)
admin_site.register(Message, BotRelatedAdmin)
admin_site.register(Bloger, BlogerAdmin)
admin_site.register(ScheduledMessage, BotRelatedAdmin)
admin_site.register(Campain, BotRelatedAdmin)
admin_site.register(Bot, BotAdmin)
admin_site.register(Folder, FolderAdmin)