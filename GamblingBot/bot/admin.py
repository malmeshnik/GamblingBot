from django.contrib import admin

from .models import *


@admin.register(ScheduledMessage)
class ScheduledMessageAdmin(admin.ModelAdmin):
    list_display = ['text', 'button_text', 'send_at', 'sent']

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'username', 'bloger')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['text', 'button_text']

    # def has_add_permission(self, request):
    #     return False
    
@admin.register(Bloger)
class BlogerAdmin(admin.ModelAdmin):
    list_display = ['name', 'invited_people', 'ref_link_to_site', 'ref_link_to_bot']

@admin.register(Campain)
class CampainAdmin(admin.ModelAdmin):
    list_display = ['text', 'button_text', 'delay_minutes']