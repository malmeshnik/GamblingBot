from django.db import models
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.html import escape

class UserStatus(models.TextChoices):
    ACTIVE = "active", "Активний"
    BLOCKED = "blocked", "Заблокував бота"
    DELETED = "deleted", "Видалив акаунт"
    FORBIDDEN = "forbidden", "Інша помилка"

class User(models.Model):
    bot = models.ForeignKey('Bot', on_delete=models.CASCADE)
    telegram_id = models.BigIntegerField(
        null=False, blank=False, verbose_name="Телеграм ID"
    )
    username = models.CharField(
        null=True, blank=True, max_length=100, verbose_name="Юзернейм"
    )
    first_name = models.CharField(
        null=True, blank=True, max_length=100, verbose_name="Ім'я"
    )
    last_name = models.CharField(
        null=True, blank=True, max_length=100, verbose_name="Фамілія"
    )
    bloger = models.ForeignKey(
        "Bloger",
        related_name="users",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Блогер який запросив",
    )

    status = models.CharField(
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE,
        verbose_name="Статус користувача"
    )

    joined_at = models.DateTimeField(verbose_name="Додався в", auto_now_add=True)

    def __str__(self):
        return self.first_name
    
    class Meta:
        verbose_name = "Користувач"
        verbose_name_plural = "Користувачі"


class Message(models.Model):
    bot = models.ForeignKey('Bot', on_delete=models.CASCADE)
    text = models.TextField(max_length=1024, verbose_name="Текст повідомлення")
    media = models.FileField(
        upload_to="media/", verbose_name="Медіафайл", null=True, blank=True
    )
    button_text = models.CharField(max_length=32, verbose_name="Текст кнопки")

    class Meta:
        verbose_name = "Повідомлення"
        verbose_name_plural = "Повідомлення"


class Bloger(models.Model):
    bot = models.ForeignKey('Bot', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, verbose_name="Ім'я блогера")
    ref_link_to_site = models.URLField(verbose_name="Реферальне посилання на сайт")
    invited_people = models.IntegerField(default=0, verbose_name="Запрошено людей")
    ref_link_to_bot = models.URLField(
        null=True, blank=True, verbose_name="Реферальне посилання на бот"
    )

    class Meta:
        verbose_name = "Блогер"
        verbose_name_plural = "Блогери"

    def __str__(self):
        return f"{self.name}"


class ScheduledMessage(models.Model):
    bot = models.ForeignKey('Bot', on_delete=models.CASCADE)
    text = models.TextField(
        verbose_name="Текст повідомлення",
        help_text = mark_safe(
            "<div style='font-size:14px; color:#999;'>"
            f"{escape('Для того щоб у розсилці вказати ім\'я користувача, використайте {name}. '
                    'Підтримується HTML форматування: <b>жирний</b>, <i>курсив</i>.')}"
            "</div>"
        )
    )
    button_text = models.CharField(max_length=100, verbose_name="Текст кнопки")
    button_link = models.URLField(
        blank=True,
        null=True,
        verbose_name="Посилання кнопки",
        help_text=mark_safe(
            """<div style='font-size:14px; color:#999;'>
            Якщо не вказати посилання, буде використанно реферальне посилання на сайт блогера, який  привів
            </div>"""
        )
    )

    media = models.FileField(
        upload_to="scheduled_media/", blank=True, null=True, verbose_name="Медіа файл"
    )

    send_at = models.DateTimeField(verbose_name="Час відправки", default=timezone.now)

    sent = models.BooleanField(default=False, verbose_name="Відправлено")

    class Meta:
        verbose_name = "Заплановане повідомлення"
        verbose_name_plural = "Заплановані повідомлення"

    def __str__(self):
        return f"{self.text[:30]}... scheduled for {self.send_at}"


class Campain(models.Model):
    bot = models.ForeignKey('Bot', on_delete=models.CASCADE)
    text = models.TextField(verbose_name="Текст повідомлення")
    button_text = models.CharField(max_length=100, verbose_name="Текст кнопки")

    media = models.FileField(
        upload_to="scheduled_media/", blank=True, null=True, verbose_name="Медіа файл"
    )
    delay_minutes = models.PositiveIntegerField(
        verbose_name="Затримка у хвилинах", default=0
    )

    class Meta:
        verbose_name = "Повідомлення після старту"
        verbose_name_plural = "Повідомлення після старту"


class MessageAfterStart(models.Model):
    bot = models.ForeignKey('Bot', on_delete=models.CASCADE)
    text = models.TextField(verbose_name="Текст повідомлення")
    button_text = models.CharField(max_length=100, verbose_name="Текст кнопки")
    user = models.ForeignKey("User", on_delete=models.CASCADE)

    media = models.FileField(
        upload_to="scheduled_media/", blank=True, null=True, verbose_name="Медіа файл"
    )

    send_at = models.DateTimeField(verbose_name="Час відправки", default=timezone.now)

    sent = models.BooleanField(default=False, verbose_name="Відправлено")

class Bot(models.Model):
    name = models.CharField(max_length=100, verbose_name="Назва бота")
    token = models.CharField(max_length=255, verbose_name="Токен")
    # bot_id = models.BigIntegerField(
    #     blank=True, 
    #     null=True, 
    #     verbose_name='ID бота',
    #     help_text='ID визначається автоматично його не потрібно заповнювати'
    # )
    # username = models.CharField(
    #     max_length=100,
    #     blank=True,
    #     null=True,
    #     verbose_name='Юзернейм бота',
    #     help_text='Юзернейм визначається автоматично'
    # )
    # button_text = models.CharField(null=True, blank=True,max_length=100, verbose_name='Назва кнопки для miniapp')
    # miniapp_link = models.URLField(null=True, blank=True, verbose_name='Посилання на сайт для miniapp')
    # created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Бот'
        verbose_name_plural = 'Боти'

class BotStatistics(models.Model):
    class Meta:
        managed = False
        verbose_name = "Статистика бота"
        verbose_name_plural = "Статистика бота"