"""
Утилита для конвертации валют
"""
from forex_python.converter import CurrencyRates
from django.core.cache import cache
from decimal import Decimal


# Маппинг стран на валюты
COUNTRY_CURRENCY_MAP = {
    'kz': 'KZT',  # Казахстан -> тенге
    'uz': 'UZS',  # Узбекистан -> сум
    'ru': 'RUB',  # Россия -> рубль
}

# Базовые цены в сумах (для Узбекистана)
BASE_PRICES_UZS = {
    'gold': Decimal('30000'),
    'premium': Decimal('50000'),
    'vip': Decimal('100000'),
}

# Цена верификации в долларах
VERIFICATION_PRICE_USD = Decimal('15.00')


def get_currency_for_country(country_code: str) -> str:
    """
    Возвращает код валюты для страны
    
    Args:
        country_code: Код страны (kz, uz, ru)
        
    Returns:
        Код валюты (KZT, UZS, RUB)
    """
    return COUNTRY_CURRENCY_MAP.get(country_code.lower(), 'UZS')


# Fallback курсы валют (используются для мгновенной загрузки)
FALLBACK_RATES = {
    ('USD', 'UZS'): 12500.0,
    ('USD', 'KZT'): 450.0,
    ('USD', 'RUB'): 90.0,
    ('UZS', 'KZT'): 0.036,
    ('UZS', 'RUB'): 0.0072,
    ('KZT', 'RUB'): 0.2,
    # Обратные курсы
    ('UZS', 'USD'): 1.0 / 12500.0,
    ('KZT', 'USD'): 1.0 / 450.0,
    ('RUB', 'USD'): 1.0 / 90.0,
    ('KZT', 'UZS'): 1.0 / 0.036,
    ('RUB', 'UZS'): 1.0 / 0.0072,
    ('RUB', 'KZT'): 1.0 / 0.2,
}


def _get_exchange_rate_fast(from_currency: str, to_currency: str) -> float:
    """
    Быстрое получение курса валют из fallback или кэша.
    Не делает внешних запросов - использует только кэш или fallback.
    """
    if from_currency == to_currency:
        return 1.0
    
    cache_key = f'exchange_rate_{from_currency}_{to_currency}'
    rate = cache.get(cache_key)
    
    if rate is not None:
        return float(rate)
    
    # Используем fallback курсы для мгновенной работы
    key = (from_currency, to_currency)
    if key in FALLBACK_RATES:
        rate = FALLBACK_RATES[key]
        # Сохраняем в кэш для будущего использования
        cache.set(cache_key, rate, 3600)
        return rate
    
    # Если прямого курса нет, конвертируем через USD
    usd_rate_from = FALLBACK_RATES.get(('USD', from_currency))
    usd_rate_to = FALLBACK_RATES.get(('USD', to_currency))
    
    if usd_rate_from and usd_rate_to:
        rate = usd_rate_to / usd_rate_from
        cache.set(cache_key, rate, 3600)
        return rate
    
    # Если ничего не найдено, возвращаем 1.0
    return 1.0


def convert_currency(amount: Decimal, from_currency: str, to_currency: str, use_api: bool = False) -> Decimal:
    """
    Конвертирует сумму из одной валюты в другую.
    По умолчанию использует fallback курсы для мгновенной работы.
    
    Args:
        amount: Сумма для конвертации
        from_currency: Исходная валюта (USD, UZS, KZT, RUB)
        to_currency: Целевая валюта (USD, UZS, KZT, RUB)
        use_api: Если True, пытается получить актуальный курс из API (медленно)
        
    Returns:
        Сумма в целевой валюте (округленная до 2 знаков)
    """
    if from_currency == to_currency:
        return amount
    
    # Сначала пытаемся получить из кэша или fallback (быстро)
    rate = _get_exchange_rate_fast(from_currency, to_currency)
    
    # Если запрошено обновление через API (опционально, в фоне)
    if use_api:
        cache_key = f'exchange_rate_{from_currency}_{to_currency}'
        try:
            c = CurrencyRates()
            api_rate = c.get_rate(from_currency, to_currency)
            # Обновляем кэш с актуальным курсом
            cache.set(cache_key, api_rate, 3600)
            rate = api_rate
        except Exception:
            # Если API недоступен, используем уже полученный fallback курс
            pass
    
    result = amount * Decimal(str(rate))
    return result.quantize(Decimal('0.01'))


def convert_usd_to_uzs(amount_usd: float) -> Decimal:
    """
    Конвертирует доллары США в узбекские сумы.
    Использует кэширование курса валют на 1 час.
    
    Args:
        amount_usd: Сумма в долларах США
        
    Returns:
        Сумма в узбекских сумах (округленная до 2 знаков)
    """
    return convert_currency(Decimal(str(amount_usd)), 'USD', 'UZS')


def get_promotion_price_for_country(plan: str, country_code: str) -> Decimal:
    """
    Возвращает цену тарифа продвижения для указанной страны
    
    Args:
        plan: Тариф (gold, premium, vip)
        country_code: Код страны (kz, uz, ru)
        
    Returns:
        Цена в валюте страны
    """
    base_price_uzs = BASE_PRICES_UZS.get(plan)
    if not base_price_uzs:
        return Decimal('0')
    
    target_currency = get_currency_for_country(country_code)
    
    # Если страна Узбекистан, возвращаем базовую цену
    if country_code.lower() == 'uz':
        return base_price_uzs
    
    # Конвертируем из UZS в валюту страны
    return convert_currency(base_price_uzs, 'UZS', target_currency)


def get_verification_price_for_country(country_code: str) -> tuple[Decimal, Decimal]:
    """
    Возвращает цену верификации для указанной страны
    
    Args:
        country_code: Код страны (kz, uz, ru)
        
    Returns:
        Кортеж (цена в валюте страны, цена в USD)
    """
    try:
        target_currency = get_currency_for_country(country_code)
        price_in_currency = convert_currency(VERIFICATION_PRICE_USD, 'USD', target_currency)
        return price_in_currency, VERIFICATION_PRICE_USD
    except Exception as e:
        # В случае ошибки возвращаем дефолтное значение в сумах
        # Это предотвратит падение страницы
        fallback_price = convert_currency(VERIFICATION_PRICE_USD, 'USD', 'UZS')
        return fallback_price, VERIFICATION_PRICE_USD
