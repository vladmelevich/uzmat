from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.db.models import Q, Count, Sum, F
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.utils.text import slugify
from django.utils import timezone
from django.db import transaction
from django.db.models import Case, When, Value, IntegerField
from django.conf import settings as django_settings
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
import os
import logging
from .models import (
    User,
    Advertisement,
    Favorite,
    Category,
    AdvertisementImage,
    VerificationRequest,
    ChatThread,
    ChatMessage,
    ChatImage,
)
from .utils.currency import (
    convert_usd_to_uzs,
    get_promotion_price_for_country,
    get_verification_price_for_country,
    get_currency_for_country,
)
from .utils.click_payment import verify_click_signature, generate_click_payment_url
from .utils.security import (
    sanitize_string,
    validate_email,
    validate_phone,
    sanitize_search_query,
    check_sql_injection_patterns,
)
from decimal import Decimal, InvalidOperation
from itertools import chain


def index(request):
    """Главная страница со списком объявлений (только продажа и аренда)"""
    from django.core.cache import cache
    from .utils.background_tasks import run_in_background, bump_ads_async
    
    now = timezone.now()
    
    # Автоподнятие каждые 3 часа (выполняется АСИНХРОННО в фоновом потоке)
    # Используем кэш для предотвращения частых обновлений
    last_bump_key = 'last_bump_update'
    last_bump_time = cache.get(last_bump_key)
    
    if not last_bump_time or (now - last_bump_time).total_seconds() > 300:  # Каждые 5 минут максимум
        # Запускаем обновление в фоновом потоке (НЕ блокирует ответ)
        run_in_background(bump_ads_async)
        cache.set(last_bump_key, now, 300)  # Кэшируем на 5 минут
    
    # На /catalog/ фильтрация работает через get_filtered_ads(). На главной тоже применяем те же GET-фильтры
    # (в первую очередь country/city из селектора), но оставляем только sale/rent.
    # Оптимизация: используем select_related и only для загрузки только нужных полей
    base_active = (get_filtered_ads(request)
                   .filter(ad_type__in=['sale', 'rent'])
                   .select_related('user')
                   .prefetch_related('images')
                   .annotate(bump_order=Coalesce('last_bumped_at', 'created_at')))
    
    promoted_active = base_active.filter(
        is_promoted=True,
        promotion_until__gte=now
    )
    
    verified_active = base_active.filter(
        user__is_verified=True,
        user__verified_until__gte=now
    )
    
    plan_priority = Case(
        When(promotion_plan='vip', then=Value(1)),
        When(promotion_plan='premium', then=Value(2)),
        When(promotion_plan='gold', then=Value(3)),
        default=Value(4),
        output_field=IntegerField()
    )
    
    HOT_LIMIT = 16
    POPULAR_LIMIT = 10
    
    # Горячие предложения: до 16 по приоритету тарифа, затем по времени продвижения; дальше проверенные
    # Оптимизация: используем only для загрузки только нужных полей
    hot_promoted = list(
        promoted_active.annotate(plan_priority=plan_priority)
        .only('id', 'title', 'slug', 'price', 'currency', 'city', 'country', 'ad_type', 
              'promoted_at', 'created_at', 'promotion_plan', 'user_id', 'image')
        .order_by('plan_priority', '-promoted_at', '-created_at')[:HOT_LIMIT]
    )
    hot_ids = [ad.id for ad in hot_promoted]
    slots_left = max(0, HOT_LIMIT - len(hot_promoted))
    hot_verified = []
    if slots_left > 0:
        hot_verified = list(
            verified_active.exclude(id__in=hot_ids)
            .only('id', 'title', 'slug', 'price', 'currency', 'city', 'country', 'ad_type',
                  'created_at', 'user_id', 'image')
            .order_by('-user__verified_until', '-bump_order')[:slots_left]
        )
        hot_ids.extend([ad.id for ad in hot_verified])
    hot_offers = hot_promoted + hot_verified
    
    if not hot_offers:
        hot_offers = list(base_active.only('id', 'title', 'slug', 'price', 'currency', 'city', 
                                          'country', 'ad_type', 'created_at', 'user_id', 'image')
                         .order_by('-bump_order')[:7])
    
    # Популярные: до 10, GOLD держится в топ-4 первые 12 часов, далее общий приоритет VIP > PREMIUM > GOLD, затем проверенные
    # Оптимизация: используем only для загрузки только нужных полей
    fresh_gold = list(
        promoted_active.filter(
            promotion_plan='gold',
            promoted_at__gte=now - timezone.timedelta(hours=12)
        ).only('id', 'title', 'slug', 'price', 'currency', 'city', 'country', 'ad_type',
               'promoted_at', 'created_at', 'user_id', 'image')
        .order_by('-promoted_at')[:4]
    )
    
    exclude_ids = [ad.id for ad in fresh_gold]
    rest_popular = list(
        promoted_active.exclude(id__in=exclude_ids)
        .annotate(plan_priority=plan_priority)
        .only('id', 'title', 'slug', 'price', 'currency', 'city', 'country', 'ad_type',
              'promoted_at', 'created_at', 'promotion_plan', 'user_id', 'image')
        .order_by('plan_priority', '-promoted_at', '-created_at')[: max(0, POPULAR_LIMIT - len(fresh_gold))]
    )
    exclude_ids.extend([ad.id for ad in rest_popular])
    
    verified_popular = list(
        verified_active.exclude(id__in=exclude_ids)
        .only('id', 'title', 'slug', 'price', 'currency', 'city', 'country', 'ad_type',
              'created_at', 'user_id', 'image')
        .order_by('-user__verified_until', '-bump_order')[: max(0, POPULAR_LIMIT - len(fresh_gold) - len(rest_popular))]
    )
    
    popular_ads = (fresh_gold + rest_popular + verified_popular)[:POPULAR_LIMIT]
    
    # Общая подборка на главной (превью)
    ads = list(base_active.only('id', 'title', 'slug', 'price', 'currency', 'city', 'country', 
                                'ad_type', 'created_at', 'user_id', 'image')
              .order_by('-bump_order')[:8])
    
    # Подсчитываем непрочитанные сообщения для авторизованных пользователей
    # Оптимизация: используем кэширование и ограничиваем количество запросов
    unread_count = 0
    if request.user.is_authenticated:
        me = request.user
        cache_key = f'unread_count_{me.id}'
        cached_unread = cache.get(cache_key)
        
        if cached_unread is not None:
            unread_count = cached_unread
        else:
            # Оптимизированный подсчет: получаем только нужные треды
            threads = ChatThread.objects.filter(
                Q(buyer=me) | Q(seller=me)
            ).select_related('buyer', 'seller')[:100]  # Ограничиваем количество
            
            thread_ids = [t.id for t in threads]
            if thread_ids:
                # Получаем все непрочитанные сообщения одним запросом
                buyer_threads = [t.id for t in threads if t.buyer_id == me.id]
                seller_threads = [t.id for t in threads if t.seller_id == me.id]
                
                # Подсчитываем непрочитанные для покупателя
                if buyer_threads:
                    buyer_unread = ChatMessage.objects.filter(
                        thread_id__in=buyer_threads
                    ).exclude(sender=me).filter(
                        Q(thread__buyer_last_read_at__isnull=True) |
                        Q(created_at__gt=F('thread__buyer_last_read_at'))
                    ).count()
                    unread_count += buyer_unread
                
                # Подсчитываем непрочитанные для продавца
                if seller_threads:
                    seller_unread = ChatMessage.objects.filter(
                        thread_id__in=seller_threads
                    ).exclude(sender=me).filter(
                        Q(thread__seller_last_read_at__isnull=True) |
                        Q(created_at__gt=F('thread__seller_last_read_at'))
                    ).count()
                    unread_count += seller_unread
            
            # Кэшируем результат на 30 секунд (асинхронно)
            from .utils.background_tasks import run_in_background, update_unread_count_cache_async
            run_in_background(update_unread_count_cache_async, me.id, unread_count)
    
    context = {
        'user': request.user,
        'ads': ads,
        'hot_offers': hot_offers,
        'popular_ads': popular_ads,
        'unread_messages_count': unread_count,
    }
    return render(request, 'uzmat/index.html', context)


def ad_detail(request, slug):
    """Страница детального просмотра объявления"""
    # Получаем объявление без фильтра по is_active
    ad = get_object_or_404(Advertisement, slug=slug)
    
    # Проверяем доступ: если объявление неактивно, только владелец может его просматривать
    if not ad.is_active:
        if not request.user.is_authenticated or ad.user != request.user:
            from django.http import Http404
            raise Http404("Объявление не найдено")
    
    # Увеличиваем счетчик просмотров только для активных объявлений или для владельца
    # Оптимизация: выполняем АСИНХРОННО в фоновом потоке (не блокирует запрос)
    if ad.is_active or (request.user.is_authenticated and ad.user == request.user):
        from .utils.background_tasks import run_in_background, increment_ad_views_async
        
        user_ip = request.META.get("REMOTE_ADDR", "unknown")
        # Запускаем обновление счетчика в фоновом потоке
        run_in_background(increment_ad_views_async, ad.id, user_ip)
        # Обновляем объект в памяти (может быть немного устаревшим, но это нормально)
        ad.refresh_from_db()
    
    # Проверяем, добавлено ли в избранное
    is_favorited = False
    if request.user.is_authenticated:
        is_favorited = Favorite.objects.filter(user=request.user, advertisement=ad).exists()
    
    # Получаем другие объявления того же пользователя (только активные для публичного просмотра)
    if request.user.is_authenticated and ad.user == request.user:
        # Владелец видит все свои объявления
        other_ads = Advertisement.objects.filter(
            user=ad.user
        ).exclude(pk=ad.pk).exclude(slug='').exclude(slug__isnull=True).select_related('user')[:3]
    else:
        # Другие пользователи видят только активные объявления
        other_ads = Advertisement.objects.filter(
            user=ad.user, 
            is_active=True
        ).exclude(pk=ad.pk).exclude(slug='').exclude(slug__isnull=True).select_related('user')[:3]
    
    # Количество объявлений пользователя (для владельца - все, для других - только активные)
    if request.user.is_authenticated and ad.user == request.user:
        user_ads_count = Advertisement.objects.filter(user=ad.user).count()
    else:
        user_ads_count = Advertisement.objects.filter(user=ad.user, is_active=True).count()
    
    context = {
        'ad': ad,
        'user': request.user,
        'is_favorited': is_favorited,
        'other_ads': other_ads,
        'user_ads_count': user_ads_count,
    }
    return render(request, 'uzmat/ad_detail.html', context)


def onboarding(request):
    """Страница выбора типа регистрации"""
    if request.user.is_authenticated:
        return redirect('uzmat:profile')
    return render(request, 'uzmat/onboarding.html')


def auth(request):
    """Страница входа"""
    if request.user.is_authenticated:
        return redirect('uzmat:profile')
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'login':
            # Вход
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()
            
            # Валидация входных данных (защита от SQL инъекций и XSS)
            if not email or not password:
                if is_ajax:
                    return JsonResponse({'success': False, 'message': 'Заполните все поля'}, status=400)
                messages.error(request, 'Заполните все поля', extra_tags='auth')
                return render(request, 'uzmat/auth.html')
            
            # Валидация email с использованием утилиты безопасности
            if not validate_email(email):
                if is_ajax:
                    return JsonResponse({'success': False, 'message': 'Неверный формат email'}, status=400)
                messages.error(request, 'Неверный формат email', extra_tags='auth')
                return render(request, 'uzmat/auth.html')
            
            # Проверка на SQL инъекции (дополнительная защита)
            if check_sql_injection_patterns(email) or check_sql_injection_patterns(password):
                if is_ajax:
                    return JsonResponse({'success': False, 'message': 'Обнаружены недопустимые символы'}, status=400)
                messages.error(request, 'Обнаружены недопустимые символы', extra_tags='auth')
                return render(request, 'uzmat/auth.html')
            
            # Проверка длины пароля
            if len(password) > 128:
                if is_ajax:
                    return JsonResponse({'success': False, 'message': 'Пароль слишком длинный'}, status=400)
                messages.error(request, 'Пароль слишком длинный', extra_tags='auth')
                return render(request, 'uzmat/auth.html')
            
            # Django ORM автоматически защищает от SQL инъекций через параметризованные запросы
            user = authenticate(request, username=email, password=password)
            if user:
                # Успешный вход - сбрасываем счетчик попыток
                from django.core.cache import cache
                ip_address = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] if request.META.get('HTTP_X_FORWARDED_FOR') else request.META.get('REMOTE_ADDR', '')
                if ip_address:
                    cache.delete(f'login_attempts_{ip_address}')
                    cache.delete(f'rate_limit_login_{ip_address}')
                
                login(request, user)
                if is_ajax:
                    return JsonResponse({'success': True, 'message': 'Вход выполнен успешно!', 'redirect': reverse('uzmat:profile')})
                messages.success(request, 'Вход выполнен успешно!', extra_tags='auth')
                return redirect('uzmat:profile')
            else:
                if is_ajax:
                    return JsonResponse({'success': False, 'message': 'Неверный email или пароль'}, status=400)
                messages.error(request, 'Неверный email или пароль', extra_tags='auth')
                return render(request, 'uzmat/auth.html')
    
    return render(request, 'uzmat/auth.html')


def register_individual(request):
    """Регистрация физического лица"""
    if request.user.is_authenticated:
        return redirect('uzmat:profile')
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        
        if not name or not email or not password:
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'Заполните все обязательные поля'}, status=400)
            messages.error(request, 'Заполните все обязательные поля', extra_tags='auth')
            return render(request, 'uzmat/auth.html', {'show_register': True})
        
        if User.objects.filter(email=email).exists():
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'Пользователь с таким email уже существует'}, status=400)
            messages.error(request, 'Пользователь с таким email уже существует', extra_tags='auth')
            return render(request, 'uzmat/auth.html', {'show_register': True})
        
        # Создаем пользователя и сразу логиним
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name,
            account_type='individual'
        )
        
        # Сразу логиним пользователя
        login(request, user)
        if is_ajax:
            return JsonResponse({'success': True, 'message': 'Регистрация успешно завершена! Добро пожаловать в Uzmat!', 'redirect': reverse('uzmat:profile')})
        messages.success(request, 'Регистрация успешно завершена! Добро пожаловать в Uzmat!', extra_tags='auth')
        return redirect('uzmat:profile')
    
    # Если GET запрос, показываем страницу регистрации
    return render(request, 'uzmat/auth.html', {'show_register': True})


def register_company(request):
    """Регистрация компании"""
    if request.user.is_authenticated:
        return redirect('uzmat:profile')
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == 'POST':
        company_name = request.POST.get('company_name', '').strip()
        company_inn = request.POST.get('company_inn', '').strip()
        company_director = request.POST.get('company_director', '').strip()
        company_phone = request.POST.get('company_phone', '').strip()
        company_email = request.POST.get('company_email', '').strip()
        company_address = request.POST.get('company_address', '').strip()
        company_legal_address = request.POST.get('company_legal_address', '').strip()
        company_website = request.POST.get('company_website', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        
        # Проверка обязательных полей
        if not all([company_name, company_inn, company_director, company_phone, company_email, email, password]):
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'Заполните все обязательные поля'}, status=400)
            messages.error(request, 'Заполните все обязательные поля', extra_tags='auth')
            return render(request, 'uzmat/register_company.html')
        
        # Проверка на дубликаты
        if User.objects.filter(email=email).exists():
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'Пользователь с таким email уже существует'}, status=400)
            messages.error(request, 'Пользователь с таким email уже существует', extra_tags='auth')
            return render(request, 'uzmat/register_company.html')
        
        if User.objects.filter(company_inn=company_inn).exists():
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'Компания с таким ИНН уже зарегистрирована'}, status=400)
            messages.error(request, 'Компания с таким ИНН уже зарегистрирована', extra_tags='auth')
            return render(request, 'uzmat/register_company.html')
        
        if User.objects.filter(company_phone=company_phone).exists():
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'Компания с таким телефоном уже зарегистрирована'}, status=400)
            messages.error(request, 'Компания с таким телефоном уже зарегистрирована', extra_tags='auth')
            return render(request, 'uzmat/register_company.html')
        
        if User.objects.filter(company_email=company_email).exists():
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'Компания с таким email уже зарегистрирована'}, status=400)
            messages.error(request, 'Компания с таким email уже зарегистрирована', extra_tags='auth')
            return render(request, 'uzmat/register_company.html')
        
        # Создаем пользователя для компании и сразу логиним
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=company_director,
            account_type='company',
            company_name=company_name,
            company_inn=company_inn,
            company_director=company_director,
            company_phone=company_phone,
            company_email=company_email,
            company_address=company_address if company_address else None,
            company_legal_address=company_legal_address if company_legal_address else None,
            company_website=company_website if company_website else None,
        )
        
        # Сразу логиним пользователя
        login(request, user)
        if is_ajax:
            return JsonResponse({'success': True, 'message': 'Регистрация успешно завершена! Добро пожаловать в Uzmat!', 'redirect': reverse('uzmat:profile')})
        messages.success(request, 'Регистрация успешно завершена! Добро пожаловать в Uzmat!', extra_tags='auth')
        return redirect('uzmat:profile')
    
    return render(request, 'uzmat/register_company.html')


@login_required(login_url='/onboarding/')
def profile(request):
    """Страница профиля пользователя"""
    if request.method == 'POST':
        # Обновление профиля
        user = request.user
        
        # Обработка загрузки аватара
        if 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']
        
        user.first_name = request.POST.get('name', user.first_name)
        user.city = request.POST.get('city', user.city)
        user.phone = request.POST.get('phone', user.phone)
        
        # Если это компания, обновляем данные компании
        if user.account_type == 'company':
            user.company_name = request.POST.get('company_name', user.company_name)
            user.company_inn = request.POST.get('company_inn', user.company_inn)
            user.company_director = request.POST.get('company_director', user.company_director)
            user.company_phone = request.POST.get('company_phone', user.company_phone)
            user.company_email = request.POST.get('company_email', user.company_email)
            user.company_address = request.POST.get('company_address', user.company_address)
            user.company_legal_address = request.POST.get('company_legal_address', user.company_legal_address)
            user.company_website = request.POST.get('company_website', user.company_website)
        
        user.save()
        messages.success(request, 'Профиль обновлен!')
        return redirect('uzmat:profile')
    
    # Получаем объявления пользователя (включая неактивные - они видны только в профиле)
    user_ads = Advertisement.objects.filter(user=request.user).exclude(slug='').exclude(slug__isnull=True).select_related('user').order_by('-created_at')
    
    # Получаем избранные объявления
    favorites = Favorite.objects.filter(user=request.user).select_related('advertisement', 'advertisement__user').order_by('-created_at')
    
    context = {
        'user': request.user,
        'user_ads': user_ads,
        'favorites': favorites,
        'now_dt': timezone.now(),
    }
    return render(request, 'uzmat/profile.html', context)


def user_profile(request, user_id):
    """Публичный профиль пользователя/компании"""
    profile_user = get_object_or_404(User, id=user_id)
    
    # Получаем объявления пользователя
    user_ads = Advertisement.objects.filter(
        user=profile_user, 
        is_active=True
    ).exclude(slug='').exclude(slug__isnull=True).select_related('user').order_by('-created_at')
    
    # Количество объявлений
    ads_count = user_ads.count()
    
    # Общее количество просмотров всех объявлений
    total_views = Advertisement.objects.filter(user=profile_user, is_active=True).aggregate(
        total=Sum('views_count')
    )['total'] or 0
    
    context = {
        'profile_user': profile_user,
        'user': request.user,
        'user_ads': user_ads,
        'ads_count': ads_count,
        'total_views': total_views,
    }
    return render(request, 'uzmat/user_profile.html', context)


@ensure_csrf_cookie
@login_required
def chats(request):
    """Страница с переписками пользователя (мессенджер)"""

    me = request.user

    # Превью напоминания о продлении (для визуальной проверки)
    # Открой /chats/?preview_badge_renew=1
    if (request.GET.get('preview_badge_renew') or '').strip() == '1':
        try:
            now = timezone.now()
            # не спамим при обновлении страницы
            if not request.session.get('preview_badge_renew_sent'):
                support_agent = User.objects.filter(is_staff=True, is_active=True).order_by('id').first()
                if support_agent and support_agent.id != me.id:
                    support_thread = (ChatThread.objects
                                      .filter(thread_type='support', advertisement__isnull=True, buyer=me, seller=support_agent)
                                      .order_by('id')
                                      .first())
                    if not support_thread:
                        support_thread = ChatThread.objects.create(
                            thread_type='support',
                            advertisement=None,
                            buyer=me,
                            seller=support_agent,
                            last_message_at=now,
                        )

                    msg = ChatMessage(
                        thread=support_thread,
                        sender=support_agent,
                        system_action='renew_badge',
                        system_url=reverse('uzmat:verify_renew'),
                    )
                    msg.set_text('Превью: срок действия галочки скоро истекает. Продлите её, чтобы она не пропала.')
                    msg.save()

                    support_thread.last_message_at = msg.created_at
                    support_thread.save(update_fields=['last_message_at'])
                request.session['preview_badge_renew_sent'] = True
        except Exception:
            pass

    # Напоминание о продлении галочки: срабатывает при заходе в /chats/
    try:
        if me.is_verified_active and me.verified_until:
            remind_days = 7
            now = timezone.now()
            if me.verified_until <= now + timezone.timedelta(days=remind_days):
                if not me.badge_expiry_notified_until or me.badge_expiry_notified_until != me.verified_until:
                    support_agent = User.objects.filter(is_staff=True, is_active=True).order_by('id').first()
                    if support_agent:
                        support_thread = (ChatThread.objects
                                          .filter(thread_type='support', advertisement__isnull=True, buyer=me, seller=support_agent)
                                          .order_by('id')
                                          .first())
                        if not support_thread:
                            support_thread = ChatThread.objects.create(
                                thread_type='support',
                                advertisement=None,
                                buyer=me,
                                seller=support_agent,
                                last_message_at=now,
                            )

                        txt = f"Срок действия галочки истекает {me.verified_until.strftime('%d.%m.%Y')}. Продлите её, чтобы она не пропала."
                        msg = ChatMessage(thread=support_thread, sender=support_agent, system_action='renew_badge', system_url=reverse('uzmat:verify_renew'))
                        msg.set_text(txt)
                        msg.save()

                        support_thread.last_message_at = msg.created_at
                        support_thread.save(update_fields=['last_message_at'])

                        me.badge_expiry_notified_until = me.verified_until
                        me.save(update_fields=['badge_expiry_notified_until'])
    except Exception:
        # Не ломаем /chats/ из-за напоминаний
        pass
    threads_qs = (ChatThread.objects
               .filter(Q(buyer=me) | Q(seller=me))
               .select_related('advertisement', 'buyer', 'seller')
               .order_by('-last_message_at', '-created_at'))
    threads = list(threads_qs[:200])


    active_thread = None
    active_messages = []

    t_id = request.GET.get('t')
    if t_id:
        try:
            tid_int = int(t_id)
            active_thread = next((t for t in threads if t.id == tid_int), None)
        except (ValueError, TypeError):
            active_thread = None

    if not active_thread and threads:
        active_thread = threads[0]

    if active_thread:
        active_messages = (ChatMessage.objects
                           .filter(thread=active_thread)
                           .select_related('sender')
                           .prefetch_related('images')
                           .order_by('-created_at')[:60])
        active_messages = list(reversed(active_messages))
        
        # Помечаем тред как прочитанный при открытии
        now = timezone.now()
        if me.id == active_thread.buyer_id:
            active_thread.buyer_last_read_at = now
            active_thread.save(update_fields=['buyer_last_read_at'])
        elif me.id == active_thread.seller_id:
            active_thread.seller_last_read_at = now
            active_thread.save(update_fields=['seller_last_read_at'])

    # Подсчитываем непрочитанные сообщения для каждого треда
    unread_counts = {}
    for thread in threads:
        last_read = thread.buyer_last_read_at if me.id == thread.buyer_id else thread.seller_last_read_at
        if last_read and thread.last_message_at and thread.last_message_at > last_read:
            unread = ChatMessage.objects.filter(
                thread=thread,
                created_at__gt=last_read
            ).exclude(sender=me).count()
            if unread > 0:
                unread_counts[thread.id] = unread
        elif not last_read and thread.last_message_at:
            # Если никогда не читал, считаем все сообщения не от себя
            unread = ChatMessage.objects.filter(
                thread=thread
            ).exclude(sender=me).count()
            if unread > 0:
                unread_counts[thread.id] = unread

    context = {
        'user': me,
        'threads': threads,
        'active_thread': active_thread,
        'messages': active_messages,
        'unread_counts': unread_counts,
        'total_unread': sum(unread_counts.values()),
    }
    return render(request, 'uzmat/chats.html', context)


@login_required
def chat_start(request, ad_id: int):
    """Старт диалога по объявлению (создать/открыть)"""
    ad = get_object_or_404(Advertisement, id=ad_id)
    if ad.user_id == request.user.id:
        messages.error(request, 'Нельзя написать сообщение самому себе.')
        return redirect('uzmat:ad_detail', slug=ad.slug)

    seller = ad.user
    buyer = request.user

    thread, _ = ChatThread.objects.get_or_create(
        thread_type='ad',
        advertisement=ad,
        buyer=buyer,
        seller=seller,
        defaults={'last_message_at': timezone.now()},
    )
    return redirect(f"{reverse('uzmat:chats')}?t={thread.id}")


@login_required
def chat_send(request, thread_id: int):
    """Отправка сообщения/фото (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Метод не поддерживается'}, status=405)

    try:
        me = request.user
        thread = get_object_or_404(ChatThread.objects.select_related('advertisement', 'buyer', 'seller'), id=thread_id)
        if me.id not in (thread.buyer_id, thread.seller_id):
            return JsonResponse({'ok': False, 'error': 'Нет доступа'}, status=403)

        text = (request.POST.get('text') or '').strip()
        image = request.FILES.get('image')

        if not text and not image:
            return JsonResponse({'ok': False, 'error': 'Введите текст или прикрепите фото'}, status=400)
        
        # Санитизация текста сообщения (защита от XSS и SQL инъекций)
        if text:
            # Ограничиваем длину сообщения
            if len(text) > 5000:
                return JsonResponse({'ok': False, 'error': 'Сообщение слишком длинное (максимум 5000 символов)'}, status=400)
            
            # Проверка на SQL инъекции (дополнительная защита)
            if check_sql_injection_patterns(text):
                import logging
                logger = logging.getLogger('security')
                logger.warning(f'Обнаружена попытка SQL инъекции в сообщении чата от пользователя {me.id}')
                return JsonResponse({'ok': False, 'error': 'Сообщение содержит недопустимые символы'}, status=400)

        MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 МБ

        if image:
            # Проверяем, что файл был загружен (может быть None, если nginx отклонил запрос)
            if not hasattr(image, 'size') or image.size is None:
                return JsonResponse({'ok': False, 'error': 'Размер фотографии слишком большой. Максимальный размер: 2 МБ. Выберите файл меньшего размера.'}, status=400)
            
            content_type = getattr(image, 'content_type', '') or ''
            if not content_type.startswith('image/'):
                return JsonResponse({'ok': False, 'error': 'Можно прикреплять только изображения'}, status=400)
            
            if image.size > MAX_IMAGE_BYTES:
                size_mb = (image.size / (1024 * 1024)).toFixed(2)
                return JsonResponse({
                    'ok': False, 
                    'error': f'Размер фотографии слишком большой ({size_mb} МБ). Максимальный размер: 2 МБ. Выберите файл меньшего размера.'
                }, status=400)

        with transaction.atomic():
            msg = ChatMessage(thread=thread, sender=me)
            msg.set_text(text)
            msg.save()

            if image:
                ChatImage.objects.create(message=msg, image=image)

            thread.last_message_at = timezone.now()
            thread.save(update_fields=['last_message_at'])

        return JsonResponse({
            'ok': True,
            'message': {
                'id': msg.id,
                'sender_id': msg.sender_id,
                'text': msg.text,
                'created_at': msg.created_at.strftime('%H:%M'),
                'images': [img.image.url for img in msg.images.all()],
                'system_action': msg.system_action,
                'system_url': msg.system_url,
            }
        })
    except Exception as e:
        # Обрабатываем любые ошибки, связанные с размером файла
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ['413', 'too large', 'file size', 'request entity']):
            return JsonResponse({
                'ok': False, 
                'error': 'Размер фотографии слишком большой. Максимальный размер: 2 МБ. Выберите файл меньшего размера.'
            }, status=400)
        # Для других ошибок возвращаем общее сообщение
        return JsonResponse({
            'ok': False, 
            'error': 'Произошла ошибка при отправке сообщения. Попробуйте еще раз.'
        }, status=500)


@login_required
def chat_poll(request, thread_id: int):
    """Получение новых сообщений (AJAX polling)"""
    try:
        me = request.user
        thread = get_object_or_404(ChatThread, id=thread_id)
        if me.id not in (thread.buyer_id, thread.seller_id):
            return JsonResponse({'ok': False, 'error': 'Нет доступа'}, status=403)

        after_id = request.GET.get('after_id')
        try:
            after_id = int(after_id) if after_id else 0
        except (ValueError, TypeError):
            after_id = 0

        qs = (ChatMessage.objects
              .filter(thread=thread, id__gt=after_id)
              .select_related('sender')
              .prefetch_related('images')
              .order_by('id')[:100])

        data = []
        for m in qs:
            try:
                # Безопасное получение текста (может быть зашифрован)
                text = ''
                try:
                    text = m.text if hasattr(m, 'text') else ''
                except Exception:
                    # Если ошибка при расшифровке, оставляем пустой текст
                    text = ''
                
                # Безопасное форматирование времени
                created_at_str = ''
                try:
                    if m.created_at:
                        created_at_str = m.created_at.strftime('%H:%M')
                    else:
                        created_at_str = ''
                except (AttributeError, ValueError, TypeError):
                    created_at_str = ''
                
                # Безопасное получение URL изображений
                image_urls = []
                try:
                    for img in m.images.all():
                        if img.image:
                            image_urls.append(img.image.url)
                except Exception:
                    # Если ошибка при получении изображений, пропускаем
                    pass
                
                data.append({
                    'id': m.id,
                    'sender_id': m.sender_id,
                    'text': text,
                    'created_at': created_at_str,
                    'images': image_urls,
                    'system_action': m.system_action or '',
                    'system_url': m.system_url or '',
                })
            except Exception as e:
                # Логируем ошибку, но продолжаем обработку других сообщений
                logger = logging.getLogger('django.request')
                logger.error(f'Ошибка при обработке сообщения {m.id} в chat_poll: {str(e)}', exc_info=True)
                continue

        return JsonResponse({'ok': True, 'messages': data})
    except Exception as e:
        # Логируем общую ошибку
        logger = logging.getLogger('django.request')
        logger.error(f'Ошибка в chat_poll для thread_id={thread_id}: {str(e)}', exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Ошибка сервера'}, status=500)


@login_required
def chat_message_edit(request, message_id: int):
    """Редактирование сообщения (только автор)"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Метод не поддерживается'}, status=405)

    me = request.user
    msg = get_object_or_404(ChatMessage.objects.select_related('thread'), id=message_id)
    thread = msg.thread
    if me.id not in (thread.buyer_id, thread.seller_id):
        return JsonResponse({'ok': False, 'error': 'Нет доступа'}, status=403)
    if msg.sender_id != me.id:
        return JsonResponse({'ok': False, 'error': 'Можно редактировать только свои сообщения'}, status=403)

    text = (request.POST.get('text') or '').strip()
    if not text:
        return JsonResponse({'ok': False, 'error': 'Текст не может быть пустым'}, status=400)

    msg.set_text(text)
    msg.save(update_fields=['encrypted_text'])
    return JsonResponse({'ok': True, 'message': {'id': msg.id, 'text': msg.text}})


@login_required
def chat_message_delete(request, message_id: int):
    """Удаление сообщения (только автор)"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Метод не поддерживается'}, status=405)

    me = request.user
    msg = get_object_or_404(ChatMessage.objects.select_related('thread'), id=message_id)
    thread = msg.thread
    if me.id not in (thread.buyer_id, thread.seller_id):
        return JsonResponse({'ok': False, 'error': 'Нет доступа'}, status=403)
    if msg.sender_id != me.id:
        return JsonResponse({'ok': False, 'error': 'Можно удалять только свои сообщения'}, status=403)

    thread_id = thread.id
    msg.delete()

    # Обновим last_message_at после удаления (если надо)
    last = ChatMessage.objects.filter(thread_id=thread_id).order_by('-created_at').first()
    if last:
        ChatThread.objects.filter(id=thread_id).update(last_message_at=last.created_at)
    else:
        ChatThread.objects.filter(id=thread_id).update(last_message_at=None)

    return JsonResponse({'ok': True, 'deleted_id': message_id})


def settings(request):
    """Страница настроек аккаунта"""
    return render(request, 'uzmat/settings.html', {'user': request.user})


@login_required
def verify_renew(request):
    """Страница продления галочки (пока заглушка, контент уточнит пользователь)"""
    return render(request, 'uzmat/verify_renew.html', {'user': request.user})


@login_required
def logout_user(request):
    """Выход из аккаунта"""
    logout(request)
    messages.success(request, 'Вы успешно вышли из аккаунта', extra_tags='auth')
    return redirect('uzmat:index')


def get_filtered_ads(request, limit=None, ad_type_filter=None):
    """Вспомогательная функция для фильтрации объявлений"""
    # Оптимизация: используем select_related и prefetch_related для уменьшения количества запросов
    ads = (Advertisement.objects
           .filter(is_active=True)
           .exclude(slug='')
           .exclude(slug__isnull=True)
           .select_related('user')
           .prefetch_related('images'))
    
    # Фильтр по пользователю (для просмотра объявлений конкретного пользователя)
    user_id = request.GET.get('user')
    if user_id:
        try:
            ads = ads.filter(user_id=int(user_id))
        except (ValueError, TypeError):
            pass
    
    # Фильтр по типу объявления (если передан явно, используем его, иначе из GET)
    if ad_type_filter:
        ads = ads.filter(ad_type=ad_type_filter)
    else:
        ad_type = request.GET.get('ad_type')
        if ad_type:
            ads = ads.filter(ad_type=ad_type)
    
    # Фильтр по стране - ПРИОРИТЕТНЫЙ
    country = request.GET.get('country')
    if country:
        country = country.strip()
        if country and country != 'all' and country != '':
            # Отладочная информация
            print(f"DEBUG: Фильтрация по стране: '{country}'")
            ads = ads.filter(country=country)
            print(f"DEBUG: Количество объявлений после фильтрации по стране: {ads.count()}")
            
            # Фильтр по городу - ТОЛЬКО если выбрана страна И выбран город
            city = request.GET.get('city')
            if city and city != 'all' and city.strip():
                city = city.strip()
                print(f"DEBUG: Дополнительная фильтрация по городу: '{city}'")
                ads = ads.filter(city__icontains=city)
                print(f"DEBUG: Количество объявлений после фильтрации по стране и городу: {ads.count()}")
    else:
        # Если страна НЕ выбрана, можно фильтровать только по городу
        city = request.GET.get('city')
        if city and city != 'all' and city.strip():
            city = city.strip()
            print(f"DEBUG: Фильтрация только по городу (страна не выбрана): '{city}'")
            ads = ads.filter(city__icontains=city)
            print(f"DEBUG: Количество объявлений после фильтрации по городу: {ads.count()}")
    
    # Фильтр по типу техники
    equipment_type = request.GET.get('equipment_type')
    if equipment_type:
        ads = ads.filter(Q(equipment_type__icontains=equipment_type) | Q(part_equipment_type__icontains=equipment_type))
    
    # Фильтр по марке
    brand = request.GET.get('brand')
    if brand:
        ads = ads.filter(Q(brand__icontains=brand) | Q(part_brand__icontains=brand))
    
    # Фильтр по цене
    price_from = request.GET.get('price_from')
    price_to = request.GET.get('price_to')
    if price_from:
        try:
            ads = ads.filter(price__gte=Decimal(price_from))
        except (ValueError, TypeError):
            pass
    if price_to:
        try:
            ads = ads.filter(price__lte=Decimal(price_to))
        except (ValueError, TypeError):
            pass
    
    # Поиск по тексту (с санитизацией для защиты от SQL инъекций)
    search = request.GET.get('search')
    if search:
        # Санитизируем поисковый запрос
        search = sanitize_search_query(search)
        if search:  # Проверяем, что после санитизации запрос не пустой
            # Django ORM автоматически защищает от SQL инъекций через параметризованные запросы
            ads = ads.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(equipment_type__icontains=search) |
                Q(brand__icontains=search) |
                Q(part_name__icontains=search) |
                Q(service_name__icontains=search)
            )
    
    # Если нужен лимит, применяем его, но возвращаем QuerySet для пагинации
    if limit:
        return ads[:limit]
    
    return ads


def parts_repair(request):
    """Страница с запчастями"""
    # Всегда показываем только запчасти
    ad_type = 'parts'
    
    # Получаем объявления с применением всех фильтров
    ads = get_filtered_ads(request, ad_type_filter=ad_type)
    
    # Сохраняем общее количество до пагинации
    total_count = ads.count()
    
    # Пагинация
    paginator = Paginator(ads, 12)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_number)
    except:
        page_obj = paginator.get_page(1)
    
    # Получаем уникальные города для фильтра
    country = request.GET.get('country')
    if country and country != 'all' and country.strip():
        cities = Advertisement.objects.filter(
            is_active=True,
            country=country.strip(),
            ad_type='parts'
        ).values_list('city', flat=True).distinct().order_by('city')
    else:
        cities = Advertisement.objects.filter(
            is_active=True,
            ad_type='parts'
        ).values_list('city', flat=True).distinct().order_by('city')
    
    context = {
        'user': request.user,
        'ads': page_obj,
        'page_obj': page_obj,
        'cities': cities,
        'total_count': total_count,
    }
    return render(request, 'uzmat/parts_repair.html', context)


def check_auth(request):
    """Проверка авторизации пользователя (для AJAX)"""
    return JsonResponse({
        'authenticated': request.user.is_authenticated,
        'username': request.user.first_name or request.user.username if request.user.is_authenticated else None
    })


def help_page(request):
    """Страница помощи"""
    return render(request, 'uzmat/help.html', {'user': request.user})


def rules_page(request):
    """Страница правил"""
    return render(request, 'uzmat/rules.html', {'user': request.user})


def safety_page(request):
    """Страница безопасности"""
    return render(request, 'uzmat/safety.html', {'user': request.user})


def catalog(request):
    """Страница каталога всех объявлений (только продажа и аренда, без услуг и запчастей)"""
    # Отладочная информация
    country_param = request.GET.get('country')
    city_param = request.GET.get('city')
    ad_type_param = request.GET.get('ad_type')
    print(f"DEBUG catalog view: country={country_param}, city={city_param}, ad_type={ad_type_param}")
    print(f"DEBUG catalog view: все GET параметры: {dict(request.GET)}")
    
    # Определяем, какие типы объявлений показывать
    if not ad_type_param:
        # Если ad_type не указан - показываем ВСЕ объявления по продаже И аренде вместе
        ads = get_filtered_ads(request)
        ads = ads.filter(ad_type__in=['sale', 'rent'])
    elif ad_type_param in ['sale', 'rent']:
        # Если указан конкретный тип (sale или rent) - показываем только его
        ads = get_filtered_ads(request, ad_type_filter=ad_type_param)
    else:
        # Если указан другой тип (service, parts) - не показываем (или можно показать пустой список)
        ads = get_filtered_ads(request)
        ads = ads.none()  # Пустой QuerySet
    
    # Сохраняем общее количество до пагинации
    total_count = ads.count()
    
    # Пагинация
    paginator = Paginator(ads, 12)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_number)
    except:
        page_obj = paginator.get_page(1)
    
    # Получаем уникальные города для фильтра
    # Учитываем только объявления о продаже и аренде (без услуг и запчастей)
    country = request.GET.get('country')
    if country and country != 'all' and country.strip():
        cities_query = Advertisement.objects.filter(
            is_active=True, 
            country=country.strip(),
            ad_type__in=['sale', 'rent']
        )
    else:
        cities_query = Advertisement.objects.filter(
            is_active=True,
            ad_type__in=['sale', 'rent']
        )
    
    # Если указан конкретный ad_type, фильтруем города по нему
    if ad_type_param in ['sale', 'rent']:
        cities_query = cities_query.filter(ad_type=ad_type_param)
    
    cities = cities_query.values_list('city', flat=True).distinct().order_by('city')
    
    context = {
        'user': request.user,
        'ads': page_obj,
        'page_obj': page_obj,
        'cities': cities,
        'total_count': total_count,
    }
    return render(request, 'uzmat/catalog.html', context)


@login_required
def create_ad(request):
    """Страница создания объявления"""
    if request.method == 'POST':
        # Проверяем размер запроса до обработки (если nginx не отклонил)
        try:
            # Проверяем Content-Length заголовок
            content_length = request.META.get('CONTENT_LENGTH', '0')
            if content_length:
                try:
                    content_length = int(content_length)
                    # Если размер запроса больше 50 МБ (лимит nginx), предупреждаем
                    if content_length > 50 * 1024 * 1024:
                        messages.error(request, 'Размер загружаемых файлов слишком большой. Максимальный размер одного фото: 10 МБ. Выберите файлы меньшего размера.')
                        context = {'user': request.user}
                        return render(request, 'uzmat/create_ad.html', context)
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass  # Игнорируем ошибки проверки
        
        try:
            # Получаем данные формы
            ad_type = request.POST.get('ad_type')
            
            # Получаем заголовок и описание в зависимости от типа
            if ad_type == 'parts':
                title = request.POST.get('part_title') or request.POST.get('part_name', '')
                description = request.POST.get('part_description', '')
            elif ad_type == 'service':
                title = request.POST.get('service_name', '')
                description = request.POST.get('service_description', '')
            else:
                title = request.POST.get('title', '')
                description = request.POST.get('description', '')
            
            country = request.POST.get('country', 'kz').strip()
            city = request.POST.get('city', '').strip()
            phone = request.POST.get('phone', '').strip() or (request.user.phone if hasattr(request.user, 'phone') else '')
            
            # Валидация обязательных полей
            errors = []
            if not ad_type:
                errors.append('Выберите тип объявления')
            if not title or not title.strip():
                errors.append('Укажите заголовок объявления')
            if not description or not description.strip():
                errors.append('Укажите описание')
            if not country:
                errors.append('Выберите страну')
            if not city:
                errors.append('Выберите город')
            if not phone:
                errors.append('Укажите телефон')
            
            # Дополнительная валидация в зависимости от типа
            if ad_type in ('rent', 'sale'):
                if not request.POST.get('equipment_type'):
                    errors.append('Укажите тип техники')
                if not request.POST.get('brand'):
                    errors.append('Укажите марку')
            
            if errors:
                for error in errors:
                    messages.error(request, error)
                context = {'user': request.user}
                return render(request, 'uzmat/create_ad.html', context)
            
            # Создаем объявление
            ad = Advertisement(
                user=request.user,
                ad_type=ad_type,
                title=title.strip(),
                description=description.strip(),
                country=country,
                city=city,
                phone=phone,
                is_active=True,  # Явно устанавливаем is_active=True
            )
            
            # Заполняем поля в зависимости от типа
            if ad_type in ('rent', 'sale'):
                ad.equipment_type = request.POST.get('equipment_type', '').strip() or None
                ad.brand = request.POST.get('brand', '').strip() or None
                ad.model = request.POST.get('model', '').strip() or None
                
                year = request.POST.get('year', '').strip()
                if year:
                    try:
                        ad.year = int(year)
                    except (ValueError, TypeError):
                        pass
                
                power = request.POST.get('power', '').strip()
                if power:
                    try:
                        ad.power = int(power)
                    except (ValueError, TypeError):
                        pass
                
                weight = request.POST.get('weight', '').strip()
                if weight:
                    try:
                        # Заменяем запятую на точку и убираем пробелы
                        weight_clean = weight.replace(',', '.').replace(' ', '')
                        if weight_clean:
                            ad.weight = Decimal(weight_clean)
                        else:
                            ad.weight = None
                    except (ValueError, TypeError, InvalidOperation):
                        ad.weight = None
                else:
                    ad.weight = None
                
                ad.condition = request.POST.get('condition', '').strip() or None
                
                hours = request.POST.get('hours', '').strip()
                if hours:
                    try:
                        ad.hours = int(hours)
                    except (ValueError, TypeError):
                        pass
                
                if ad_type == 'rent':
                    ad.with_operator = request.POST.get('with_operator') == 'on'
                    ad.min_order = request.POST.get('min_order', '').strip() or None
            
            elif ad_type == 'service':
                ad.service_name = request.POST.get('service_name', '').strip() or None
            
            elif ad_type == 'parts':
                ad.part_name = request.POST.get('part_name', '').strip() or None
                ad.part_equipment_type = request.POST.get('part_equipment_type', '').strip() or None
                ad.part_brand = request.POST.get('part_brand', '').strip() or None
                ad.part_model = request.POST.get('part_model', '').strip() or None
            
            # Цена
            price = request.POST.get('price', '').strip()
            if price:
                try:
                    # Заменяем запятую на точку и убираем пробелы
                    price_clean = price.replace(',', '.').replace(' ', '').replace('\xa0', '')
                    if price_clean:
                        ad.price = Decimal(price_clean)
                    else:
                        ad.price = None
                except (ValueError, TypeError, InvalidOperation):
                    ad.price = None
            else:
                ad.price = None
            
            ad.currency = request.POST.get('currency', 'kzt')
            ad.price_type = request.POST.get('price_type', '').strip() or None
            
            # Создаем slug вручную, если его нет
            if not ad.slug or ad.slug.strip() == '':
                ad.slug = slugify(ad.title)
                if not ad.slug or ad.slug.strip() == '':
                    # Если slug все еще пустой (например, title содержит только спецсимволы)
                    ad.slug = slugify(f"ad-{ad.ad_type}-{ad.pk or 'new'}")
            
            # Убеждаемся, что slug уникален
            original_slug = ad.slug
            counter = 1
            while Advertisement.objects.filter(slug=ad.slug).exclude(pk=ad.pk).exists():
                ad.slug = f"{original_slug}-{counter}"
                counter += 1
            
            # Сохраняем объявление сначала, чтобы получить ID
            try:
                ad.save()
                # Проверяем, что объявление действительно сохранилось
                if ad.pk:
                    # Обновляем slug после сохранения, если он все еще пустой
                    if not ad.slug or ad.slug.strip() == '':
                        ad.slug = slugify(ad.title)
                        if not ad.slug:
                            ad.slug = f"ad-{ad.pk}"
                        # Проверяем уникальность
                        original_slug = ad.slug
                        counter = 1
                        while Advertisement.objects.filter(slug=ad.slug).exclude(pk=ad.pk).exists():
                            ad.slug = f"{original_slug}-{counter}"
                            counter += 1
                        ad.save(update_fields=['slug'])
                    
                    # Обработка загрузки фотографий (до 10 фотографий)
                    photos = request.FILES.getlist('photos')
                    if photos:
                        if len(photos) > 10:
                            messages.warning(request, 'Загружено больше 10 фотографий. Сохранены первые 10.')
                        
                        MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 МБ на фото
                        valid_photos = []
                        
                        for photo in photos[:10]:
                            # Проверяем, что файл был загружен (может быть None, если nginx отклонил запрос)
                            if not hasattr(photo, 'size') or photo.size is None:
                                messages.error(request, f'Файл "{getattr(photo, "name", "неизвестный")}" не был загружен. Размер файла слишком большой. Максимальный размер: 10 МБ.')
                                continue
                            
                            # Проверяем размер фото
                            if photo.size > MAX_IMAGE_SIZE:
                                size_mb = (photo.size / (1024 * 1024)).toFixed(2)
                                messages.error(request, f'Фото "{photo.name}" слишком большое ({size_mb} МБ). Максимальный размер: 10 МБ. Выберите файл меньшего размера.')
                                continue
                            
                            # Проверяем тип файла
                            content_type = getattr(photo, 'content_type', '') or ''
                            if not content_type.startswith('image/'):
                                messages.warning(request, f'Файл "{photo.name}" не является изображением. Пропущен.')
                                continue
                            
                            valid_photos.append(photo)
                        
                        # Сохраняем валидные фото
                        for index, photo in enumerate(valid_photos):
                            AdvertisementImage.objects.create(
                                advertisement=ad,
                                image=photo,
                                is_main=(index == 0),  # Первая фотография - главная
                                order=index
                            )
                    
                    messages.success(request, f'Объявление "{ad.title}" успешно создано!')
                    return redirect('uzmat:ad_detail', slug=ad.slug)
                else:
                    messages.error(request, 'Ошибка: объявление не было сохранено в базу данных')
                    context = {'user': request.user}
                    return render(request, 'uzmat/create_ad.html', context)
            except Exception as save_error:
                import traceback
                error_detail = traceback.format_exc()
                messages.error(request, f'Ошибка при сохранении объявления: {str(save_error)}')
                if django_settings.DEBUG:
                    messages.error(request, f'Детали ошибки: {error_detail}')
                context = {'user': request.user}
                return render(request, 'uzmat/create_ad.html', context)
        
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            error_msg = str(e).lower()
            
            # Проверяем, является ли это ошибкой размера файла
            if any(keyword in error_msg for keyword in [
                '413', 'too large', 'file size', 'max upload size', 
                'request entity', 'request body too large', 'content-length'
            ]):
                messages.error(request, 'Размер фотографии слишком большой. Максимальный размер одного фото: 10 МБ. Выберите файл меньшего размера.')
            else:
                messages.error(request, f'Ошибка при создании объявления: {str(e)}')
                # В режиме отладки выводим детали ошибки
                if django_settings.DEBUG:
                    messages.error(request, f'Детали: {error_detail[:500]}')
            context = {'user': request.user}
            return render(request, 'uzmat/create_ad.html', context)
    
    context = {
        'user': request.user,
    }
    return render(request, 'uzmat/create_ad.html', context)


@login_required
def edit_ad(request, slug):
    """Редактирование объявления"""
    ad = get_object_or_404(Advertisement, slug=slug)
    
    # Проверяем, что пользователь является владельцем объявления
    if ad.user != request.user:
        messages.error(request, 'У вас нет прав на редактирование этого объявления')
        return redirect('uzmat:ad_detail', slug=slug)
    
    if request.method == 'POST':
        try:
            # Получаем данные формы
            ad_type = request.POST.get('ad_type', ad.ad_type)
            
            # Получаем заголовок и описание в зависимости от типа
            if ad_type == 'parts':
                title = request.POST.get('part_title') or request.POST.get('part_name', '')
                description = request.POST.get('part_description', '')
            elif ad_type == 'service':
                title = request.POST.get('service_name', '')
                description = request.POST.get('service_description', '')
            else:
                title = request.POST.get('title', '')
                description = request.POST.get('description', '')
            
            country = request.POST.get('country', 'kz').strip()
            city = request.POST.get('city', '').strip()
            phone = request.POST.get('phone', '').strip() or (request.user.phone if hasattr(request.user, 'phone') else '')
            
            # Валидация обязательных полей
            errors = []
            if not ad_type:
                errors.append('Выберите тип объявления')
            if not title or not title.strip():
                errors.append('Укажите заголовок объявления')
            if not description or not description.strip():
                errors.append('Укажите описание')
            if not country:
                errors.append('Выберите страну')
            if not city:
                errors.append('Выберите город')
            if not phone:
                errors.append('Укажите телефон')
            
            # Дополнительная валидация в зависимости от типа
            if ad_type in ('rent', 'sale'):
                if not request.POST.get('equipment_type'):
                    errors.append('Укажите тип техники')
                if not request.POST.get('brand'):
                    errors.append('Укажите марку')
            
            if errors:
                for error in errors:
                    messages.error(request, error)
                context = {'user': request.user, 'ad': ad, 'edit_mode': True}
                return render(request, 'uzmat/create_ad.html', context)
            
            # Обновляем объявление
            ad.ad_type = ad_type
            ad.title = title.strip()
            ad.description = description.strip()
            ad.country = country
            ad.city = city
            ad.phone = phone
            
            # Заполняем поля в зависимости от типа
            if ad_type in ('rent', 'sale'):
                ad.equipment_type = request.POST.get('equipment_type', '').strip() or None
                ad.brand = request.POST.get('brand', '').strip() or None
                ad.model = request.POST.get('model', '').strip() or None
                
                year = request.POST.get('year', '').strip()
                if year:
                    try:
                        ad.year = int(year)
                    except (ValueError, TypeError):
                        ad.year = None
                else:
                    ad.year = None
                
                power = request.POST.get('power', '').strip()
                if power:
                    try:
                        ad.power = int(power)
                    except (ValueError, TypeError):
                        ad.power = None
                else:
                    ad.power = None
                
                weight = request.POST.get('weight', '').strip()
                if weight:
                    try:
                        weight_clean = weight.replace(',', '.').replace(' ', '')
                        if weight_clean:
                            ad.weight = Decimal(weight_clean)
                        else:
                            ad.weight = None
                    except (ValueError, TypeError, InvalidOperation):
                        ad.weight = None
                else:
                    ad.weight = None
                
                ad.condition = request.POST.get('condition', '').strip() or None
                
                hours = request.POST.get('hours', '').strip()
                if hours:
                    try:
                        ad.hours = int(hours)
                    except (ValueError, TypeError):
                        ad.hours = None
                else:
                    ad.hours = None
                
                if ad_type == 'rent':
                    ad.with_operator = request.POST.get('with_operator') == 'on'
                    ad.min_order = request.POST.get('min_order', '').strip() or None
                else:
                    ad.with_operator = False
                    ad.min_order = None
            
            elif ad_type == 'service':
                ad.service_name = request.POST.get('service_name', '').strip() or None
                # Очищаем поля техники
                ad.equipment_type = None
                ad.brand = None
                ad.model = None
                ad.year = None
                ad.power = None
                ad.weight = None
                ad.condition = None
                ad.hours = None
                ad.with_operator = False
                ad.min_order = None
            
            elif ad_type == 'parts':
                ad.part_name = request.POST.get('part_name', '').strip() or None
                ad.part_equipment_type = request.POST.get('part_equipment_type', '').strip() or None
                ad.part_brand = request.POST.get('part_brand', '').strip() or None
                ad.part_model = request.POST.get('part_model', '').strip() or None
                # Очищаем поля техники
                ad.equipment_type = None
                ad.brand = None
                ad.model = None
                ad.year = None
                ad.power = None
                ad.weight = None
                ad.condition = None
                ad.hours = None
                ad.with_operator = False
                ad.min_order = None
            
            # Цена
            price = request.POST.get('price', '').strip()
            if price:
                try:
                    price_clean = price.replace(',', '.').replace(' ', '').replace('\xa0', '')
                    if price_clean:
                        ad.price = Decimal(price_clean)
                    else:
                        ad.price = None
                except (ValueError, TypeError, InvalidOperation):
                    ad.price = None
            else:
                ad.price = None
            
            ad.currency = request.POST.get('currency', 'kzt')
            ad.price_type = request.POST.get('price_type', '').strip() or None
            
            # Обновляем slug, если изменился заголовок
            new_slug = slugify(ad.title)
            if new_slug and new_slug != ad.slug:
                original_slug = new_slug
                counter = 1
                while Advertisement.objects.filter(slug=new_slug).exclude(pk=ad.pk).exists():
                    new_slug = f"{original_slug}-{counter}"
                    counter += 1
                ad.slug = new_slug
            
            # Обработка изображений
            MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 МБ на фото
            
            # Основное изображение (если загружено)
            if 'image' in request.FILES:
                main_image = request.FILES['image']
                # Проверяем размер
                if main_image.size and main_image.size > MAX_IMAGE_SIZE:
                    messages.error(request, f'Основное фото слишком большое (макс. 10 МБ).')
                else:
                    # Проверяем тип файла
                    content_type = getattr(main_image, 'content_type', '') or ''
                    if content_type.startswith('image/'):
                        ad.image = main_image
                    else:
                        messages.error(request, 'Основной файл не является изображением.')
            
            # Дополнительные изображения (multiple files)
            photos = request.FILES.getlist('photos')
            if photos:
                # Ограничиваем до 10 фотографий
                if len(photos) > 10:
                    messages.warning(request, 'Загружено больше 10 фотографий. Сохранены первые 10.')
                
                # Получаем текущее количество изображений
                current_images_count = ad.images.count()
                max_images = 10 - current_images_count
                
                valid_photos = []
                for photo in photos[:max_images]:
                    # Проверяем размер фото
                    if photo.size and photo.size > MAX_IMAGE_SIZE:
                        messages.warning(request, f'Фото "{photo.name}" слишком большое (макс. 10 МБ). Пропущено.')
                        continue
                    
                    # Проверяем тип файла
                    content_type = getattr(photo, 'content_type', '') or ''
                    if not content_type.startswith('image/'):
                        messages.warning(request, f'Файл "{photo.name}" не является изображением. Пропущен.')
                        continue
                    
                    valid_photos.append(photo)
                
                # Сохраняем валидные фото
                if max_images > 0 and valid_photos:
                    for index, photo in enumerate(valid_photos[:max_images]):
                        AdvertisementImage.objects.create(
                            advertisement=ad,
                            image=photo,
                            is_main=False,
                            order=current_images_count + index
                        )
                elif max_images <= 0:
                    messages.warning(request, 'Достигнут лимит в 10 фотографий. Удалите старые фотографии, чтобы добавить новые.')
            
            ad.save()
            messages.success(request, 'Объявление успешно обновлено!')
            return redirect('uzmat:ad_detail', slug=ad.slug)
        
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            messages.error(request, f'Ошибка при обновлении объявления: {str(e)}')
            if django_settings.DEBUG:
                messages.error(request, f'Детали: {error_detail[:500]}')
            context = {'user': request.user, 'ad': ad, 'edit_mode': True}
            return render(request, 'uzmat/create_ad.html', context)
    
    # GET запрос - показываем форму редактирования
    context = {
        'user': request.user,
        'ad': ad,
        'edit_mode': True,
    }
    return render(request, 'uzmat/create_ad.html', context)


@login_required
def delete_ad(request, slug):
    """Удаление объявления"""
    ad = get_object_or_404(Advertisement, slug=slug)
    
    # Проверяем, что пользователь является владельцем объявления
    if ad.user != request.user:
        messages.error(request, 'У вас нет прав на удаление этого объявления')
        return redirect('uzmat:ad_detail', slug=slug)
    
    if request.method == 'POST':
        ad.delete()
        messages.success(request, 'Объявление успешно удалено')
        return redirect('uzmat:profile')
    
    # GET запрос - показываем страницу подтверждения
    return render(request, 'uzmat/delete_ad_confirm.html', {'ad': ad})


@login_required
def toggle_ad_status(request, slug):
    """Переключение статуса объявления (активно/неактивно)"""
    ad = get_object_or_404(Advertisement, slug=slug)
    
    # Проверяем, что пользователь является владельцем объявления
    if ad.user != request.user:
        messages.error(request, 'У вас нет прав на изменение статуса этого объявления')
        return redirect('uzmat:ad_detail', slug=slug)
    
    ad.is_active = not ad.is_active
    ad.save()
    
    status_text = 'активировано' if ad.is_active else 'деактивировано'
    
    # Если это AJAX-запрос, возвращаем JSON без перезагрузки страницы
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'is_active': ad.is_active,
            'status_text': status_text,
            'button_label': 'Неактивно' if ad.is_active else 'Активировать'
        })
    
    messages.success(request, f'Объявление успешно {status_text}')
    # Редиректим на страницу объявления (владелец всегда может просмотреть свое объявление)
    return redirect('uzmat:ad_detail', slug=slug)


@login_required
def promote_ad(request, slug):
    """Создает платеж для продвижения объявления через Click"""
    ad = get_object_or_404(Advertisement, slug=slug)
    
    if ad.user != request.user:
        messages.error(request, 'Можно продвигать только свои объявления')
        return redirect('uzmat:ad_detail', slug=slug)
    
    if request.method == 'POST':
        plan = request.POST.get('plan')
        country = request.POST.get('country') or request.GET.get('country') or 'uz'
        
        durations = {
            'gold': 3,
            'premium': 14,
            'vip': 30,
        }
        
        days = durations.get(plan)
        if not days:
            messages.error(request, 'Неизвестный тариф продвижения')
            return redirect('uzmat:promote_info', slug=slug)
        
        # Для Click всегда используем сумму в сумах (базовая цена)
        from .utils.currency import BASE_PRICES_UZS
        base_price_uzs = BASE_PRICES_UZS.get(plan, Decimal('0'))
        
        # Генерируем уникальный ID платежа (timestamp + user_id)
        import time
        payment_id = int(time.time() * 1000) + request.user.id
        
        # Сохраняем данные о платеже в кэше (не в БД, TTL 24 часа)
        from django.core.cache import cache
        payment_data = {
            'payment_type': 'promotion',
            'user_id': request.user.id,
            'ad_id': ad.id,
            'ad_slug': ad.slug,
            'plan': plan,
            'amount': str(base_price_uzs),
            'created_at': timezone.now().isoformat(),
        }
        cache.set(f'payment_{payment_id}', payment_data, 3600 * 24)  # 24 часа
        
        # Генерируем URL для оплаты (Click принимает только сумы)
        return_url = request.build_absolute_uri(reverse('uzmat:profile'))
        payment_url = generate_click_payment_url(payment_id, base_price_uzs, return_url)
        
        return redirect(payment_url)
    
    return redirect('uzmat:promote_info', slug=slug)


@login_required
def promote_info(request, slug):
    """Страница выбора тарифа продвижения"""
    ad = get_object_or_404(Advertisement, slug=slug, user=request.user)
    
    # Получаем страну из запроса или localStorage (по умолчанию uz)
    country = request.GET.get('country') or 'uz'
    
    # Получаем цены для выбранной страны
    prices = {
        'gold': get_promotion_price_for_country('gold', country),
        'premium': get_promotion_price_for_country('premium', country),
        'vip': get_promotion_price_for_country('vip', country),
    }
    
    currency_code = get_currency_for_country(country)
    
    return render(request, 'uzmat/promote_info.html', {
        'ad': ad,
        'user': request.user,
        'prices': prices,
        'currency_code': currency_code,
        'country': country,
    })


@login_required
def verify_info(request):
    """Информационная страница верификации (описание + кнопка)"""
    user = request.user

    if request.method == 'POST':
        if user.verification_status == 'pending':
            messages.info(request, 'Ваша заявка уже в обработке. Дождитесь решения модерации.')
            return redirect('uzmat:verify_info')

        v_type = (request.POST.get('verification_type') or '').strip()
        if v_type not in {'individual', 'company'}:
            v_type = 'company' if getattr(user, 'account_type', None) == 'company' else 'individual'

        # Конвертируем 15$ в сумы (для Click всегда используем сумы)
        amount_usd = Decimal('15.00')
        amount_uzs = convert_usd_to_uzs(float(amount_usd))
        
        # Генерируем уникальный ID платежа (timestamp + user_id)
        import time
        payment_id = int(time.time() * 1000) + user.id
        
        # Сохраняем данные о платеже в кэше (не в БД, TTL 24 часа)
        from django.core.cache import cache
        payment_data = {
            'payment_type': 'verification',
            'user_id': user.id,
            'verification_type': v_type,
            'amount': str(amount_uzs),
            'amount_usd': str(amount_usd),
            'created_at': timezone.now().isoformat(),
        }
        cache.set(f'payment_{payment_id}', payment_data, 3600 * 24)  # 24 часа
        
        # Генерируем URL для оплаты (Click принимает только сумы)
        return_url = request.build_absolute_uri(reverse('uzmat:verify_info'))
        payment_url = generate_click_payment_url(payment_id, amount_uzs, return_url)
        
        return redirect(payment_url)

    # Получаем страну из запроса или localStorage (по умолчанию uz)
    country = request.GET.get('country') or 'uz'
    
    
    # Получаем цену верификации для выбранной страны
    try:
        amount_in_currency, amount_usd = get_verification_price_for_country(country)
        currency_code = get_currency_for_country(country)
    except Exception:
        # В случае ошибки используем дефолтные значения
        country = 'uz'
        amount_in_currency, amount_usd = get_verification_price_for_country(country)
        currency_code = get_currency_for_country(country)

    return render(request, 'uzmat/verify_info.html', {
        'user': user,
        'amount_usd': amount_usd,
        'amount_in_currency': amount_in_currency,
        'currency_code': currency_code,
        'country': country,
    })


@staff_member_required(login_url='/auth/')
def verify_moderation_list(request):
    """Панель для администраторов: список заявок на верификацию"""
    status = (request.GET.get('status') or 'pending').strip()
    allowed_status = {'pending', 'approved', 'rejected'}
    if status not in allowed_status:
        status = 'pending'

    qs = (VerificationRequest.objects
          .select_related('user')
          .order_by('-created_at'))

    if status:
        qs = qs.filter(status=status)

    counts = {
        'pending': VerificationRequest.objects.filter(status='pending').count(),
        'approved': VerificationRequest.objects.filter(status='approved').count(),
        'rejected': VerificationRequest.objects.filter(status='rejected').count(),
    }

    return render(request, 'uzmat/verify_moderation_list.html', {
        'user': request.user,
        'requests': qs[:200],
        'status': status,
        'counts': counts,
    })


@staff_member_required(login_url='/auth/')
def verify_moderation_detail(request, request_id: int):
    """Панель для администраторов: просмотр заявки + решение"""
    v_request = get_object_or_404(
        VerificationRequest.objects.select_related('user'),
        id=request_id
    )
    target_user = v_request.user

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        comment = (request.POST.get('comment') or '').strip()

        if action not in {'approve', 'reject'}:
            messages.error(request, 'Неизвестное действие.')
            return redirect('uzmat:verify_moderation_detail', request_id=v_request.id)

        if not comment:
            messages.error(request, 'Заполните сообщение пользователю.')
            return redirect('uzmat:verify_moderation_detail', request_id=v_request.id)

        now = timezone.now()
        with transaction.atomic():
            if action == 'approve':
                v_request.status = 'approved'
                target_user.verification_status = 'approved'
                target_user.is_verified = True
                # Делаем галочку на 6 месяцев
                target_user.verified_until = now + timezone.timedelta(days=180)
            else:
                v_request.status = 'rejected'
                target_user.verification_status = 'rejected'
                target_user.is_verified = False
                target_user.verified_until = None

            v_request.reviewer_comment = comment
            v_request.reviewed_at = now
            v_request.save(update_fields=['status', 'reviewer_comment', 'reviewed_at'])

            target_user.save(update_fields=['verification_status', 'is_verified', 'verified_until'])

            # Сообщение пользователю в чат "Техподдержка (имя админа)"
            support_thread = (ChatThread.objects
                              .filter(thread_type='support', advertisement__isnull=True, buyer=target_user, seller=request.user)
                              .order_by('id')
                              .first())
            if not support_thread:
                support_thread = ChatThread.objects.create(
                    thread_type='support',
                    advertisement=None,
                    buyer=target_user,
                    seller=request.user,
                    last_message_at=now,
                )

            msg = ChatMessage(thread=support_thread, sender=request.user)
            msg.set_text(comment)
            msg.save()

            support_thread.last_message_at = msg.created_at
            support_thread.save(update_fields=['last_message_at'])

        if action == 'approve':
            messages.success(request, 'Профиль успешно верифицирован.')
        else:
            messages.success(request, 'Заявка отклонена.')

        return redirect('uzmat:verify_moderation_list')

    return render(request, 'uzmat/verify_moderation_detail.html', {
        'user': request.user,
        'v_request': v_request,
        'target_user': target_user,
    })


@staff_member_required(login_url='/auth/')
def admin_send_notification(request):
    """Админская отправка уведомлений пользователям (всем или одному) через чат техподдержки."""
    me = request.user

    if request.method == 'POST':
        target = (request.POST.get('target') or '').strip()  # all | user
        user_id = (request.POST.get('user_id') or '').strip()
        text = (request.POST.get('text') or '').strip()

        if not text:
            messages.error(request, 'Введите текст уведомления.')
            return redirect('uzmat:admin_send_notification')

        now = timezone.now()

        def send_to_user(u: User):
            if not u or not getattr(u, 'is_active', True):
                return
            if getattr(u, 'is_staff', False):
                return
            thread, _ = ChatThread.objects.get_or_create(
                thread_type='support',
                advertisement=None,
                buyer=u,
                seller=me,
                defaults={'last_message_at': now},
            )
            msg = ChatMessage(thread=thread, sender=me)
            msg.set_text(text)
            msg.save()
            thread.last_message_at = msg.created_at
            thread.save(update_fields=['last_message_at'])

        try:
            if target == 'all':
                users = User.objects.filter(is_active=True, is_staff=False).only('id')[:50000]
                sent = 0
                with transaction.atomic():
                    for u in users.iterator():
                        send_to_user(u)
                        sent += 1
                messages.success(request, f'Уведомление отправлено: {sent} пользователям.')
            else:
                try:
                    uid = int(user_id)
                except (ValueError, TypeError):
                    uid = None
                if not uid:
                    messages.error(request, 'Выберите пользователя.')
                    return redirect('uzmat:admin_send_notification')

                u = get_object_or_404(User, id=uid, is_active=True)
                with transaction.atomic():
                    send_to_user(u)
                messages.success(request, 'Уведомление отправлено пользователю.')
        except Exception:
            messages.error(request, 'Не удалось отправить уведомление. Проверьте логи сервера.')

        return redirect('uzmat:admin_send_notification')

    users = User.objects.filter(is_active=True, is_staff=False).order_by('id')[:2000]
    return render(request, 'uzmat/admin_send_notification.html', {
        'user': me,
        'users': users,
    })


@login_required
def toggle_favorite(request, ad_id):
    """Добавить/удалить объявление из избранного"""
    if request.method == 'POST':
        try:
            ad = get_object_or_404(Advertisement, pk=ad_id, is_active=True)
            favorite, created = Favorite.objects.get_or_create(user=request.user, advertisement=ad)
            
            if not created:
                favorite.delete()
                return JsonResponse({'status': 'removed', 'is_favorited': False})
            else:
                return JsonResponse({'status': 'added', 'is_favorited': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


def privacy_policy(request):
    """Страница политики конфиденциальности"""
    context = {
        'user': request.user,
    }
    return render(request, 'uzmat/privacy_policy.html', context)


def terms_of_use(request):
    """Страница условий использования"""
    context = {
        'user': request.user,
    }
    return render(request, 'uzmat/terms_of_use.html', context)


def sitemap(request):
    """Страница карты сайта"""
    context = {
        'user': request.user,
    }
    return render(request, 'uzmat/sitemap.html', context)


def logistics(request):
    """Страница ремонта - показывает все объявления типа 'service'"""
    # Получаем объявления типа 'service' с применением фильтров
    ads = get_filtered_ads(request, ad_type_filter='service')
    
    # Сохраняем общее количество до пагинации
    total_count = ads.count()
    
    # Пагинация
    paginator = Paginator(ads, 12)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_number)
    except:
        page_obj = paginator.get_page(1)
    
    # Получаем уникальные города для фильтра
    country = request.GET.get('country')
    if country and country != 'all' and country.strip():
        cities = Advertisement.objects.filter(
            is_active=True, 
            country=country.strip(),
            ad_type='service'
        ).values_list('city', flat=True).distinct().order_by('city')
    else:
        cities = Advertisement.objects.filter(
            is_active=True,
            ad_type='service'
        ).values_list('city', flat=True).distinct().order_by('city')
    
    context = {
        'active_tab': 'services',
        'user': request.user,
        'ads': page_obj,
        'page_obj': page_obj,
        'cities': cities,
        'total_count': total_count,
    }
    return render(request, 'uzmat/logistics.html', context)


@login_required
def add_cargo(request):
    """Страница добавления груза"""
    context = {
        'user': request.user,
    }
    return render(request, 'uzmat/add_cargo.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def click_webhook(request):
    """
    Webhook для обработки callback от Click платежной системы
    Использует кэш вместо БД для хранения данных о платежах
    """
    from django.core.cache import cache
    
    try:
        # Получаем параметры из запроса
        merchant_trans_id = request.POST.get('merchant_trans_id', '')
        click_trans_id = request.POST.get('click_trans_id', '')
        amount = request.POST.get('amount', '')
        action = int(request.POST.get('action', '0'))
        sign_time = request.POST.get('sign_time', '')
        sign_string = request.POST.get('sign_string', '')
        merchant_prepare_id = request.POST.get('merchant_prepare_id', '')
        error = request.POST.get('error', '')
        error_note = request.POST.get('error_note', '')
        
        # Получаем данные о платеже из кэша
        try:
            payment_id = int(merchant_trans_id)
            payment_data = cache.get(f'payment_{payment_id}')
            
            if not payment_data:
                return JsonResponse({
                    'error': -5,
                    'error_note': 'Invalid merchant_trans_id'
                })
        except (ValueError, TypeError):
            return JsonResponse({
                'error': -5,
                'error_note': 'Invalid merchant_trans_id'
            })
        
        # Проверяем подпись
        amount_decimal = Decimal(amount)
        if not verify_click_signature(
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id or '',
            amount=amount_decimal,
            action=action,
            sign_time=sign_time,
            sign_string=sign_string
        ):
            return JsonResponse({
                'error': -1,
                'error_note': 'Invalid signature'
            })
        
        # Обрабатываем действия
        if action == 0:  # Prepare
            # Проверяем сумму
            expected_amount = Decimal(payment_data['amount'])
            if amount_decimal != expected_amount:
                return JsonResponse({
                    'error': -2,
                    'error_note': 'Invalid amount'
                })
            
            # Сохраняем prepare_id в кэш
            payment_data['click_payment_id'] = merchant_prepare_id
            cache.set(f'payment_{payment_id}', payment_data, 3600 * 24)  # 24 часа
            
            return JsonResponse({
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'merchant_prepare_id': merchant_prepare_id,
                'error': 0,
                'error_note': 'Success'
            })
        
        elif action == 1:  # Complete
            # Проверяем сумму
            expected_amount = Decimal(payment_data['amount'])
            if amount_decimal != expected_amount:
                return JsonResponse({
                    'error': -2,
                    'error_note': 'Invalid amount'
                })
            
            # Обрабатываем в зависимости от типа платежа
            with transaction.atomic():
                payment_type = payment_data.get('payment_type')
                
                if payment_type == 'promotion':
                    # Активируем продвижение объявления
                    ad_id = payment_data.get('ad_id')
                    plan = payment_data.get('plan')
                    
                    if ad_id and plan:
                        try:
                            ad = Advertisement.objects.get(id=ad_id)
                            durations = {
                                'gold': 3,
                                'premium': 14,
                                'vip': 30,
                            }
                            days = durations.get(plan, 0)
                            if days > 0:
                                now = timezone.now()
                                ad.is_promoted = True
                                ad.promoted_at = now
                                ad.promotion_until = now + timezone.timedelta(days=days)
                                ad.promotion_plan = plan
                                ad.save(update_fields=['is_promoted', 'promoted_at', 'promotion_until', 'promotion_plan'])
                        except Advertisement.DoesNotExist:
                            pass
                
                elif payment_type == 'verification':
                    # Создаем заявку на верификацию
                    user_id = payment_data.get('user_id')
                    v_type = payment_data.get('verification_type', 'individual')
                    
                    if user_id:
                        try:
                            user = User.objects.get(id=user_id)
                            
                            VerificationRequest.objects.create(
                                user=user,
                                verification_type=v_type,
                                status='pending',
                            )
                            
                            user.verification_type = v_type
                            user.verification_status = 'pending'
                            user.is_verified = False
                            user.verified_until = None
                            user.save(update_fields=['verification_type', 'verification_status', 'is_verified', 'verified_until'])
                        except User.DoesNotExist:
                            pass
            
            # Удаляем данные о платеже из кэша после успешной обработки
            cache.delete(f'payment_{payment_id}')
            
            return JsonResponse({
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'merchant_confirm_id': merchant_trans_id,
                'error': 0,
                'error_note': 'Success'
            })
        
        elif action == -1:  # Cancel
            # Удаляем данные о платеже из кэша при отмене
            cache.delete(f'payment_{payment_id}')
            
            return JsonResponse({
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'error': 0,
                'error_note': 'Success'
            })
        
        else:
            return JsonResponse({
                'error': -8,
                'error_note': 'Action not found'
            })
    
    except Exception as e:
        return JsonResponse({
            'error': -9,
            'error_note': f'System error: {str(e)}'
        })
