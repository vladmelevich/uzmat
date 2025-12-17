from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.text import slugify
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class User(AbstractUser):
    """Расширенная модель пользователя"""
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="Город")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Аватар")
    is_verified = models.BooleanField(default=False, verbose_name="Проверенный профиль")
    verified_until = models.DateTimeField(blank=True, null=True, verbose_name="Галочка активна до")
    verification_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[('individual', 'Физическое лицо'), ('company', 'Компания')],
        verbose_name="Тип верификации"
    )
    verification_status = models.CharField(
        max_length=20,
        default='none',
        choices=[
            ('none', 'Нет заявки'),
            ('pending', 'В обработке'),
            ('approved', 'Одобрено'),
            ('rejected', 'Отклонено'),
        ],
        verbose_name="Статус верификации"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    badge_expiry_notified_until = models.DateTimeField(blank=True, null=True, verbose_name="Напоминание о продлении отправлено для срока до")

    @property
    def is_verified_active(self) -> bool:
        """Активная галочка (как в Instagram): is_verified + срок не истёк."""
        if not self.is_verified:
            return False
        if not self.verified_until:
            return False
        return self.verified_until >= timezone.now()
    
    # Тип аккаунта
    account_type = models.CharField(
        max_length=20,
        choices=[('individual', 'Физическое лицо'), ('company', 'Компания')],
        default='individual',
        verbose_name='Тип аккаунта'
    )
    
    # Поля компании
    company_name = models.CharField(max_length=200, blank=True, null=True, verbose_name='Название компании')
    company_inn = models.CharField(max_length=20, blank=True, null=True, verbose_name='ИНН')
    company_director = models.CharField(max_length=200, blank=True, null=True, verbose_name='Директор')
    company_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Телефон компании')
    company_email = models.EmailField(max_length=254, blank=True, null=True, verbose_name='Email компании')
    company_address = models.TextField(blank=True, null=True, verbose_name='Адрес компании')
    company_legal_address = models.TextField(blank=True, null=True, verbose_name='Юридический адрес')
    company_website = models.URLField(blank=True, null=True, verbose_name='Сайт компании')
    company_description = models.TextField(blank=True, null=True, verbose_name='Описание компании')

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.username or self.email or f"User {self.id}"


class Category(models.Model):
    """Категория объявлений"""
    name = models.CharField(max_length=100, verbose_name="Название")
    slug = models.SlugField(unique=True, verbose_name="URL")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='children', verbose_name="Родительская категория")
    
    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Advertisement(models.Model):
    """Модель объявления"""
    AD_TYPE_CHOICES = [
        ('rent', 'Аренда'),
        ('sale', 'Продажа'),
        ('service', 'Услуги'),
        ('parts', 'Запчасти'),
    ]
    
    PRICE_TYPE_CHOICES = [
        ('per-hour', 'За час'),
        ('per-day', 'За день'),
        ('per-month', 'За месяц'),
        ('fixed', 'Договорная'),
    ]
    
    CONDITION_CHOICES = [
        ('new', 'Новое'),
        ('excellent', 'Отличное'),
        ('good', 'Хорошее'),
        ('satisfactory', 'Удовлетворительное'),
    ]
    
    CURRENCY_CHOICES = [
        ('kzt', '₸ KZT'),
        ('uzs', 'сум UZS'),
        ('rub', '₽ RUB'),
        ('byn', 'Br BYN'),
    ]
    
    # Основная информация
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='advertisements', verbose_name="Пользователь")
    ad_type = models.CharField(max_length=20, choices=AD_TYPE_CHOICES, verbose_name="Тип объявления")
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    slug = models.SlugField(unique=True, max_length=200, verbose_name="URL")
    description = models.TextField(verbose_name="Описание")
    
    # Категория
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Категория")
    
    # Для техники (аренда/продажа)
    equipment_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="Тип техники")
    brand = models.CharField(max_length=100, blank=True, null=True, verbose_name="Марка")
    model = models.CharField(max_length=100, blank=True, null=True, verbose_name="Модель")
    year = models.IntegerField(blank=True, null=True, verbose_name="Год выпуска")
    
    # Для услуг
    service_name = models.CharField(max_length=200, blank=True, null=True, verbose_name="Название услуги")
    
    # Для запчастей
    part_name = models.CharField(max_length=200, blank=True, null=True, verbose_name="Название запчасти")
    part_equipment_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="Для какого типа техники")
    part_brand = models.CharField(max_length=100, blank=True, null=True, verbose_name="Марка для запчасти")
    part_model = models.CharField(max_length=100, blank=True, null=True, verbose_name="Модель для запчасти")
    
    # Местоположение
    country = models.CharField(max_length=10, default='kz', verbose_name="Страна")
    city = models.CharField(max_length=100, verbose_name="Город")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    
    # Цена
    price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="Цена")
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='kzt', verbose_name="Валюта")
    price_type = models.CharField(max_length=20, choices=PRICE_TYPE_CHOICES, blank=True, null=True, verbose_name="Тип цены")
    
    # Для аренды
    with_operator = models.BooleanField(default=False, verbose_name="С оператором")
    min_order = models.CharField(max_length=100, blank=True, null=True, verbose_name="Минимальный заказ")
    
    # Характеристики
    power = models.IntegerField(blank=True, null=True, verbose_name="Мощность (л.с.)")
    weight = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Вес (т)")
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True, null=True, verbose_name="Состояние")
    hours = models.IntegerField(blank=True, null=True, verbose_name="Часы работы")
    
    # Изображение
    image = models.ImageField(upload_to='advertisements/', blank=True, null=True, verbose_name="Фотография объявления", help_text="Загрузите фотографию для объявления")
    
    # Статус
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    views_count = models.IntegerField(default=0, verbose_name="Количество просмотров")
    is_promoted = models.BooleanField(default=False, verbose_name="Продвинуто")
    promoted_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата продвижения")
    promotion_until = models.DateTimeField(blank=True, null=True, verbose_name="Активно до")
    promotion_plan = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[
            ('gold', 'GOLD'),
            ('premium', 'PREMIUM'),
            ('vip', 'VIP'),
        ],
        verbose_name="Тариф продвижения"
    )
    last_bumped_at = models.DateTimeField(blank=True, null=True, verbose_name="Последнее поднятие")
    
    # Даты
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Объявление"
        verbose_name_plural = "Объявления"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ad_type', 'is_active']),
            models.Index(fields=['city', 'country']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Убеждаемся, что slug уникален
            original_slug = self.slug
            counter = 1
            while Advertisement.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('uzmat:ad_detail', kwargs={'slug': self.slug})
    
    def get_price_display(self):
        """Форматированное отображение цены"""
        if not self.price:
            return "Договорная"
        
        currency_symbols = {
            'kzt': '₸',
            'uzs': 'сум',
            'rub': '₽',
            'byn': 'Br',
        }
        
        symbol = currency_symbols.get(self.currency, '')
        # Для аренды показываем тариф, для остальных типов — без суффиксов
        if self.ad_type == 'rent':
            if self.price_type == 'per-hour':
                return f"{self.price:,.0f} {symbol}/час".replace(',', ' ')
            elif self.price_type == 'per-day':
                return f"{self.price:,.0f} {symbol}/день".replace(',', ' ')
            elif self.price_type == 'per-month':
                return f"{self.price:,.0f} {symbol}/месяц".replace(',', ' ')
        return f"{self.price:,.0f} {symbol}".replace(',', ' ')
    
    def get_country_display(self):
        """Отображение названия страны"""
        countries = {
            'kz': 'Казахстан',
            'uz': 'Узбекистан',
            'ru': 'Россия',
            'by': 'Беларусь',
        }
        return countries.get(self.country, 'Казахстан')


class AdvertisementImage(models.Model):
    """Фотографии объявлений"""
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='images', verbose_name="Объявление")
    image = models.ImageField(upload_to='advertisements/', verbose_name="Фотография")
    is_main = models.BooleanField(default=False, verbose_name="Главное изображение")
    order = models.IntegerField(default=0, verbose_name="Порядок")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Фотография объявления"
        verbose_name_plural = "Фотографии объявлений"
        ordering = ['is_main', 'order', 'created_at']
    
    def __str__(self):
        return f"Фото для {self.advertisement.title}"


class Favorite(models.Model):
    """Избранные объявления"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites', verbose_name="Пользователь")
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='favorited_by', verbose_name="Объявление")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    
    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        unique_together = ['user', 'advertisement']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user} - {self.advertisement.title}"


class VerificationRequest(models.Model):
    """Заявка на верификацию профиля"""
    TYPE_CHOICES = [
        ('individual', 'Физическое лицо'),
        ('company', 'Юридическое лицо'),
    ]
    STATUS_CHOICES = [
        ('pending', 'В обработке'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='verification_requests', verbose_name='Пользователь')
    verification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='Тип верификации')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Статус')
    reviewer_comment = models.TextField(blank=True, null=True, verbose_name='Комментарий модератора')
    reviewed_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата решения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Заявка на верификацию'
        verbose_name_plural = 'Заявки на верификацию'
        ordering = ['-created_at']

    def __str__(self):
        return f"Заявка #{self.id} ({self.get_verification_type_display()}) — {self.user}"


def _chat_fernet() -> Fernet:
    # Детерминированный ключ из SECRET_KEY (для dev/простоты).
    # Важно: если SECRET_KEY сменится, старые сообщения расшифровать нельзя.
    raw = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


class ChatThread(models.Model):
    """Диалог: по объявлению или с техподдержкой"""
    THREAD_TYPE_CHOICES = [
        ('ad', 'По объявлению'),
        ('support', 'Техподдержка'),
    ]

    thread_type = models.CharField(max_length=20, choices=THREAD_TYPE_CHOICES, default='ad', verbose_name='Тип чата')
    advertisement = models.ForeignKey('Advertisement', on_delete=models.CASCADE, related_name='chat_threads', verbose_name='Объявление', blank=True, null=True)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_threads_as_buyer', verbose_name='Покупатель')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_threads_as_seller', verbose_name='Продавец')
    last_message_at = models.DateTimeField(blank=True, null=True, verbose_name='Время последнего сообщения')
    buyer_last_read_at = models.DateTimeField(blank=True, null=True, verbose_name='Время последнего прочтения покупателем')
    seller_last_read_at = models.DateTimeField(blank=True, null=True, verbose_name='Время последнего прочтения продавцом')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Чат'
        verbose_name_plural = 'Чаты'
        constraints = [
            models.UniqueConstraint(fields=['thread_type', 'advertisement', 'buyer', 'seller'], name='unique_chat_by_type_ad_and_users'),
        ]
        ordering = ['-last_message_at', '-created_at']

    def __str__(self):
        if self.thread_type == 'support':
            return f"Чат #{self.id} (support) {self.buyer_id}->{self.seller_id}"
        return f"Чат #{self.id} по {self.advertisement_id}"

    def other_user(self, me):
        return self.seller if me_id(me) == self.buyer_id else self.buyer


def me_id(me):
    try:
        return me.id
    except Exception:
        return None


class ChatMessage(models.Model):
    """Сообщение в чате (текст хранится зашифрованным)"""
    SYSTEM_ACTION_CHOICES = [
        ('renew_badge', 'Продлить галочку'),
    ]

    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages', verbose_name='Чат')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_messages', verbose_name='Отправитель')
    encrypted_text = models.TextField(blank=True, null=True, verbose_name='Текст (зашифрованный)')
    system_action = models.CharField(max_length=50, blank=True, null=True, choices=SYSTEM_ACTION_CHOICES, verbose_name='Системное действие')
    system_url = models.CharField(max_length=500, blank=True, null=True, verbose_name='URL действия')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата отправки')

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']

    def __str__(self):
        return f"Сообщение #{self.id} в чате #{self.thread_id}"

    def set_text(self, plain: str):
        plain = (plain or '').strip()
        if not plain:
            self.encrypted_text = None
            return
        token = _chat_fernet().encrypt(plain.encode('utf-8'))
        self.encrypted_text = token.decode('utf-8')

    def get_text(self) -> str:
        if not self.encrypted_text:
            return ''
        try:
            plain = _chat_fernet().decrypt(self.encrypted_text.encode('utf-8'))
            return plain.decode('utf-8')
        except (InvalidToken, ValueError, TypeError):
            # Если кто-то записал plaintext напрямую (например, через админку),
            # не прячем сообщение. Но если это похоже на fernet-токен — не показываем "мусор".
            raw = (self.encrypted_text or '').strip()
            if raw.startswith('gAAAA'):
                return ''
            return raw

    @property
    def text(self) -> str:
        return self.get_text()


class ChatImage(models.Model):
    """Вложение к сообщению: только изображения"""
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='images', verbose_name='Сообщение')
    image = models.ImageField(upload_to='chat/images/', verbose_name='Изображение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')

    class Meta:
        verbose_name = 'Фото в чате'
        verbose_name_plural = 'Фото в чате'
        ordering = ['created_at']

    def __str__(self):
        return f"Фото #{self.id} для сообщения #{self.message_id}"
