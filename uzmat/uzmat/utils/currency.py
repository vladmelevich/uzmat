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
    'by': 'BYN',  # Беларусь -> белорусский рубль
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
        country_code: Код страны (kz, uz, ru, by)
        
    Returns:
        Код валюты (KZT, UZS, RUB, BYN)
    """
    return COUNTRY_CURRENCY_MAP.get(country_code.lower(), 'UZS')


def convert_currency(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    """
    Конвертирует сумму из одной валюты в другую.
    Использует кэширование курса валют на 1 час.
    
    Args:
        amount: Сумма для конвертации
        from_currency: Исходная валюта (USD, UZS, KZT, RUB, BYN)
        to_currency: Целевая валюта (USD, UZS, KZT, RUB, BYN)
        
    Returns:
        Сумма в целевой валюте (округленная до 2 знаков)
    """
    if from_currency == to_currency:
        return amount
    
    cache_key = f'exchange_rate_{from_currency}_{to_currency}'
    rate = cache.get(cache_key)
    
    if rate is None:
        try:
            c = CurrencyRates()
            rate = c.get_rate(from_currency, to_currency)
            # Кэшируем на 1 час (3600 секунд)
            cache.set(cache_key, rate, 3600)
        except Exception as e:
            # Если не удалось получить курс, используем примерные курсы
            fallback_rates = {
                ('USD', 'UZS'): 12500.0,
                ('USD', 'KZT'): 450.0,
                ('USD', 'RUB'): 90.0,
                ('USD', 'BYN'): 3.2,
                ('UZS', 'KZT'): 0.036,
                ('UZS', 'RUB'): 0.0072,
                ('UZS', 'BYN'): 0.000256,
                ('KZT', 'RUB'): 0.2,
                ('KZT', 'BYN'): 0.0071,
                ('RUB', 'BYN'): 0.0356,
            }
            # Проверяем обратный курс
            reverse_key = (to_currency, from_currency)
            if reverse_key in fallback_rates:
                rate = 1.0 / fallback_rates[reverse_key]
            elif (from_currency, to_currency) in fallback_rates:
                rate = fallback_rates[(from_currency, to_currency)]
            else:
                # Если курса нет, конвертируем через USD
                usd_rate_from = fallback_rates.get(('USD', from_currency), 1.0)
                usd_rate_to = fallback_rates.get(('USD', to_currency), 1.0)
                if usd_rate_from and usd_rate_to:
                    rate = usd_rate_to / usd_rate_from
                else:
                    rate = 1.0
            
            cache.set(cache_key, rate, 3600)
    
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
        country_code: Код страны (kz, uz, ru, by)
        
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
        country_code: Код страны (kz, uz, ru, by)
        
    Returns:
        Кортеж (цена в валюте страны, цена в USD)
    """
    target_currency = get_currency_for_country(country_code)
    price_in_currency = convert_currency(VERIFICATION_PRICE_USD, 'USD', target_currency)
    return price_in_currency, VERIFICATION_PRICE_USD
