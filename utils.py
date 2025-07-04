import random
import yfinance as yf
from typing import List
import os
import openai
from datetime import datetime, timedelta

# Список популярных акций и ETF с их описаниями
STOCKS = {
    # "VOO": "S&P 500 ETF - индексный фонд, отслеживающий 500 крупнейших компаний США",  # Удалено по запросу
    "VTI": "Total Stock Market ETF - индексный фонд всего рынка США",
    "QQQ": "Nasdaq-100 ETF - индексный фонд технологических компаний",
    "AAPL": "Apple - технологическая компания, производитель iPhone и Mac",
    "MSFT": "Microsoft - технологическая компания, разработчик Windows и Office",
    "GOOGL": "Alphabet (Google) - технологическая компания, владелец поисковой системы Google",
    "AMZN": "Amazon - технологическая компания, крупнейший онлайн-ритейлер",
    "TSLA": "Tesla - производитель электромобилей и солнечных панелей",
    "NVDA": "NVIDIA - производитель графических процессоров и чипов для ИИ",
    "BRK-B": "Berkshire Hathaway - инвестиционная компания Уоррена Баффета"
}

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_random_stock_with_history(start_year: int) -> str:
    """
    Выбирает случайную акцию, по которой есть исторические данные с указанного года.
    Если таких нет — возвращает None.
    """
    available_stocks = []
    start_date = f"{start_year}-01-01"
    for symbol in STOCKS.keys():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, period="1mo")
            if not hist.empty:
                available_stocks.append(symbol)
        except Exception:
            continue
    if available_stocks:
        return random.choice(available_stocks)
    return None

def get_random_stock(start_year: int = None) -> str:
    """
    Если указан start_year — выбирает только акции с историей с этого года.
    Иначе — случайную из всех доступных.
    """
    if start_year:
        stock = get_random_stock_with_history(start_year)
        if stock:
            return stock
    # fallback: случайная из всех
    available_stocks = []
    for symbol in STOCKS.keys():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")
            if not hist.empty:
                available_stocks.append(symbol)
        except Exception:
            continue
    if not available_stocks:
        return "AAPL"  # fallback
    return random.choice(available_stocks)

def get_stock_info(symbol: str) -> dict:
    """
    Получает информацию об акции
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        return {
            "name": info.get("longName", symbol),
            "sector": info.get("sector", "Неизвестно"),
            "industry": info.get("industry", "Неизвестно"),
            "description": STOCKS.get(symbol, "Нет описания"),
            "current_price": info.get("currentPrice", 0),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", 0),
            "dividend_yield": info.get("dividendYield", 0),
            "beta": info.get("beta", 0)
        }
    except Exception:
        return {
            "name": symbol,
            "description": STOCKS.get(symbol, "Нет описания"),
            "error": "Не удалось получить дополнительную информацию"
        }

def format_currency(amount: float, currency: str = '') -> str:
    """Format amount with currency as plain text, without .00 for integers."""
    if amount == int(amount):
        amount_str = f"{int(amount):,}".replace(",", " ")  # неразрывный пробел
    else:
        amount_str = f"{amount:,.2f}".replace(",", " ")
    if currency:
        return f"{amount_str} {currency}"
    return f"{amount_str}"

def format_percentage(value: float) -> str:
    """Format value as percentage with 2 decimal places."""
    return f"{value:.2f}%"

async def validate_with_ai(user_input: str, stage: str) -> dict:
    """
    Валидация пользовательского ввода с помощью OpenAI GPT.
    stage: one of ['year', 'habit', 'currency', 'amount']
    Возвращает: {'is_valid': bool, 'reason': str, 'suggestion': str}
    """
    prompts = {
        'year': "Пользователь должен ввести год начала работы (например, 2010). Вот его ответ: '{input}'. Это корректный год? Если нет — объясни, почему, и приведи пример корректного ответа.",
        'habit': "Пользователь должен кратко описать вредную привычку (например, курение, алкоголь, сладкое). Вот его ответ: '{input}'. Это корректное описание привычки? Если нет — объясни, почему, и приведи пример корректного ответа.",
        'currency': "Пользователь должен ввести реальную валюту (например, рубли, доллары, евро, тенге, драм, USD, EUR, RUB, AMD). Вот его ответ: '{input}'. Это корректная валюта? Если нет — объясни, почему, и приведи пример корректного ответа.",
        'amount': "Пользователь должен ввести сумму трат в день (например, 500, 5.50, 1000). Вот его ответ: '{input}'. Это корректная сумма? Если нет — объясни, почему, и приведи пример корректного ответа."
    }
    prompt = prompts.get(stage, '').format(input=user_input)
    if not prompt:
        return {'is_valid': True, 'reason': '', 'suggestion': ''}
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты помощник, который валидирует пользовательский ввод для финансового бота. Отвечай строго в формате JSON: {\"is_valid\": true/false, \"reason\": \"...\", \"suggestion\": \"...\"}"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0
        )
        import json
        content = response.choices[0].message.content
        # Попробуем найти JSON в ответе
        start = content.find('{')
        end = content.rfind('}') + 1
        json_str = content[start:end]
        return json.loads(json_str)
    except Exception as e:
        return {'is_valid': True, 'reason': '', 'suggestion': ''}  # fallback: пропускаем 

def words_to_number(text: str) -> float:
    """
    Пробует распознать число, написанное словами (русский и английский, простые случаи).
    Возвращает float или None.
    """
    # Примитивная реализация для самых частых случаев
    # Можно расширить по необходимости
    num_words = {
        # Русский
        "ноль": 0, "один": 1, "два": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9,
        "десять": 10, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
        "сто": 100, "двести": 200, "триста": 300, "четыреста": 400, "пятьсот": 500, "шестьсот": 600, "семьсот": 700, "восемьсот": 800, "девятьсот": 900,
        "тысяча": 1000, "тысячи": 1000, "тысяч": 1000,
        # Английский
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
        "hundred": 100, "thousand": 1000
    }
    words = text.lower().replace('-', ' ').split()
    total = 0
    current = 0
    for word in words:
        if word in num_words:
            scale = num_words[word]
            if scale == 1000:
                if current == 0:
                    current = 1
                total += current * 1000
                current = 0
            elif scale == 100:
                if current == 0:
                    current = 1
                current *= 100
            else:
                current += scale
    total += current
    return float(total) if total > 0 else None 