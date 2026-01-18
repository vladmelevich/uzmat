from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User,
    Advertisement,
    Favorite,
    Category,
    VerificationRequest,
    ChatThread,
    ChatMessage,
    ChatImage,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'city', 'phone', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'date_joined')
    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительная информация', {'fields': ('phone', 'city', 'avatar')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Дополнительная информация', {'fields': ('phone', 'city')}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent')
    list_filter = ('parent',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'ad_type', 'city', 'price', 'is_active', 'sent_to_telegram', 'created_at', 'views_count')
    list_filter = ('ad_type', 'is_active', 'country', 'city', 'sent_to_telegram', 'created_at')
    search_fields = ('title', 'description', 'city', 'brand', 'equipment_type')
    readonly_fields = ('created_at', 'updated_at', 'views_count', 'telegram_message_id')
    date_hierarchy = 'created_at'
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'ad_type', 'title', 'slug', 'description', 'category', 'image', 'is_active')
        }),
        ('Техника', {
            'fields': ('equipment_type', 'brand', 'model', 'year', 'power', 'weight', 'condition', 'hours'),
            'classes': ('collapse',)
        }),
        ('Услуги', {
            'fields': ('service_name',),
            'classes': ('collapse',)
        }),
        ('Запчасти', {
            'fields': ('part_name', 'part_equipment_type', 'part_brand', 'part_model'),
            'classes': ('collapse',)
        }),
        ('Местоположение', {
            'fields': ('country', 'city', 'phone')
        }),
        ('Цена', {
            'fields': ('price', 'currency', 'price_type', 'with_operator', 'min_order')
        }),
        ('Telegram', {
            'fields': ('sent_to_telegram', 'telegram_message_id'),
            'classes': ('collapse',)
        }),
        ('Статистика', {
            'fields': ('views_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'advertisement', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'advertisement__title')
    date_hierarchy = 'created_at'


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'verification_type', 'status', 'created_at', 'reviewed_at')
    list_filter = ('verification_type', 'status', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name')
    readonly_fields = ('created_at',)


class ChatImageInline(admin.TabularInline):
    model = ChatImage
    extra = 0
    fields = ('image', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ('id', 'advertisement', 'buyer', 'seller', 'last_message_at', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('advertisement__title', 'buyer__username', 'seller__username', 'buyer__email', 'seller__email')
    readonly_fields = ('created_at',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'thread', 'sender', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('thread__advertisement__title', 'sender__username', 'sender__email')
    readonly_fields = ('created_at',)
    inlines = (ChatImageInline,)

