import os
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from states import InvestmentStates
from utils import get_random_stock, words_to_number, get_stock_info, format_currency
from calculator import calculate_investment
from openai import AsyncOpenAI
from datetime import datetime
import re

router = Router()

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = (
    "Ты — жёстко сфокусированный, дружелюбный, но требовательный финансовый ассистент. "
    "Твой стиль: коротко, с юмором, без формул и математики, только результат и мотивация. "
    "Всегда выводи все ключевые числа и название акции явно, не скрывай их. "
    "Не объясняй расчёты, не используй англицизмы, не философствуй."
)

# --- RESULT PROMPT ---
RESULT_PROMPT = (
    "Пользователь с {year} года тратил {daily_spend} {currency} в день на {habit}. "
    "Если бы он ежемесячно инвестировал эти деньги в {symbol}, то сегодня у него было бы {total_value:,} {currency}. "
    "Всего потрачено: {total_invested:,} {currency}. Итоговая сумма инвестиций: {total_value:,} {currency}. "
    "Упущенная выгода: {missed_profit:,} {currency}. "
    "Процент прибыли: {profit_percent:.1f}%. CAGR: {cagr:.1f}%. Волатильность: {volatility:.1f}% (если доступно).\n"
    "В финальном сообщении обязательно выведи: название акции, итоговую сумму инвестиций, сколько всего потрачено, сколько мог бы заработать, и разницу (упущенная выгода) — всё с подписями и в явном виде, с юмором и мотивацией. Не показывай математику, только результат."
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

CURRENCIES = ["RUB", "USD", "EUR", "AMD", "KZT", "UAH", "BYN", "GBP", "CNY"]
CONFIRM_WORDS = ["да", "готов", "ок", "согласен", "yes", "go"]

# --- START ---
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(InvestmentStates.waiting_for_year)
    await message.answer("Привет! Я финансовый ассистент Константина. Давай начнем)\nС какого года ты начал работать и получать зарплату? (укажи год в цифрах)")

# --- YEAR ---
@router.message(InvestmentStates.waiting_for_year)
async def process_year(message: Message, state: FSMContext):
    year_match = re.search(r"\d{4}", message.text)
    if year_match:
        year = int(year_match.group())
        if 1970 <= year <= datetime.now().year:
            await state.update_data(year=year)
            await state.set_state(InvestmentStates.waiting_for_habits)
            await message.answer("Хорошо, спасибо за информацию. Какая вредная привычка у тебя есть?")
            return
    # Если не найдено — пробуем распознать числа словами или транслитом (можно доработать позже)
    await message.answer(f"Пожалуйста, укажи год цифрами от 1970 до {datetime.now().year}")

# --- HABITS ---
@router.message(InvestmentStates.waiting_for_habits)
async def process_habits(message: Message, state: FSMContext):
    habit = message.text.strip().lower()
    # Отклоняем слишком короткие, пустые или бессмысленные ответы
    if len(habit) < 2 or habit in ["нет", "-"] or habit.isdigit():
        await message.answer("Опиши привычку чуть подробнее!")
        return
    await state.update_data(habit=habit)
    await state.set_state(InvestmentStates.waiting_for_daily_cost)
    await message.answer("Сколько примерно ты тратишь на эту вредную привычку в день?")

# --- DAILY COST ---
@router.message(InvestmentStates.waiting_for_daily_cost)
async def process_daily_cost(message: Message, state: FSMContext):
    text = message.text.lower().replace(",", ".")
    # Пробуем найти число в тексте
    match = re.search(r"[\d.]+", text)
    daily_spend = None
    if match:
        try:
            daily_spend = float(match.group())
        except Exception:
            pass
    # Если не найдено — пробуем распознать сумму словами (рус/англ)
    if daily_spend is None:
        daily_spend = words_to_number(text)
    if not daily_spend or daily_spend <= 0:
        await message.answer("Пожалуйста, укажи сумму в день (например: 500 или пятьсот)")
        return
    await state.update_data(daily_spend=daily_spend)
    await state.set_state(InvestmentStates.waiting_for_currency)
    await message.answer("В какой валюте ты тратишь эти деньги?")

# --- CURRENCY ---
@router.message(InvestmentStates.waiting_for_currency)
async def process_currency(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    # Словарь синонимов валют
    currency_map = {
        "usd": ["usd", "доллар", "доллары", "dollar", "dollars", "бакс", "баксы"],
        "eur": ["eur", "евро", "euro"],
        "rub": ["rub", "рубль", "руб", "рубли", "ruble", "rubles"],
        "amd": ["amd", "драм", "dram"],
        "kzt": ["kzt", "тенге", "tenge"],
        "uah": ["uah", "гривна", "гривны", "hryvnia"],
        "byn": ["byn", "белрубль", "бел.рубль", "белорусский рубль", "byrub", "byr"],
        "gbp": ["gbp", "фунт", "фунты", "pound", "pounds"],
        "cny": ["cny", "юань", "yuan"]
    }
    currency_code = None
    for code, synonyms in currency_map.items():
        if any(s in text for s in synonyms):
            currency_code = code.upper()
            break
    if not currency_code:
        await message.answer("Пожалуйста, выбери валюту из списка: USD, EUR, RUB, AMD, KZT, UAH, BYN, GBP, CNY")
        return
    await state.update_data(currency=currency_code)
    data = await state.get_data()
    monthly = int(data["daily_spend"] * 30)
    await state.set_state(InvestmentStates.waiting_for_confirmation)
    await message.answer(f"Ты тратишь примерно {monthly} {currency_code} в месяц. Готов откладывать такую сумму?")

def generate_final_message(symbol, stock_info, habit, year, daily_spend, currency, total_value, total_invested, missed_profit, profit_percent):
    # Словарь склонений и уникальных фраз для популярных привычек
    habit_data = {
        "сигареты": {
            "habit_acc": "сигареты",
            "habit_prep": "на сигареты",
            "joke": "Мог бы дышать полной грудью и купить себе яхту!"
        },
        "кофе": {
            "habit_acc": "кофе",
            "habit_prep": "на кофе",
            "joke": "Мог бы открыть свою кофейню!"
        },
        "алкоголь": {
            "habit_acc": "алкоголь",
            "habit_prep": "на алкоголь",
            "joke": "Мог бы купить виноградник и пить только своё!"
        },
        "девочки": {
            "habit_acc": "девочек",
            "habit_prep": "на девочек",
            "joke": "Мог бы купить себе остров и пригласить всех!"
        },
        "фастфуд": {
            "habit_acc": "фастфуд",
            "habit_prep": "на фастфуд",
            "joke": "Мог бы открыть свою бургерную!"
        },
        "сладкое": {
            "habit_acc": "сладкое",
            "habit_prep": "на сладкое",
            "joke": "Мог бы построить шоколадную фабрику!"
        }
    }
    h = habit.lower()
    for key in habit_data:
        if key in h:
            hd = habit_data[key]
            break
    else:
        hd = {"habit_acc": habit, "habit_prep": f"на {habit}", "joke": "Мог бы инвестировать с умом!"}
    # Юмор по году
    if int(year) < 2000:
        year_joke = f"С {year} года ты мог бы стать легендой инвестиций!"
    elif int(year) < 2010:
        year_joke = f"С {year} года ты бы уже мог купить квартиру!"
    else:
        year_joke = f"С {year} года ты мог бы накопить на мечту!"
    return (
        f"💡 {symbol} ({stock_info.get('description', symbol)})\n\n"
        f"🚬 Вместо {hd['habit_acc']} ты мог бы инвестировать {format_currency(daily_spend, currency)} в день в {symbol} с {year} года.\n"
        f"💰 Сегодня у тебя было бы: {format_currency(total_value, currency)}!\n\n"
        f"🔥 Вместо того чтобы потратить {format_currency(total_invested, currency)} {hd['habit_prep']}, ты мог бы заработать +{format_currency(missed_profit, currency)}!\n"
        f"📈 Это целых {profit_percent:.1f}% прибыли!\n\n"
        f"❗️ Не упусти возможность увеличить свой капитал! {hd['joke']} {year_joke}\n\n"
        f"🤓 Если хочешь быть умнее, чем ты был в {year} — углубись в инвестиции, следи за моим инстаграмом!\n\n"
        f"🚨 У тебя есть вредные привычки, которые съедают твои деньги. Пора задуматься!\n\n"
        f"*Все цифры примерные, расчёт основан только на динамике актива, без учёта валютных колебаний.*"
    )

# --- CONFIRMATION ---
@router.message(InvestmentStates.waiting_for_confirmation)
async def process_confirmation(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if not any(word in text for word in CONFIRM_WORDS):
        await message.answer("Если готов — напиши 'да', 'готов', 'ок' или предложи свою сумму!")
        return
    data = await state.get_data()
    year = data["year"]
    daily_spend = data["daily_spend"]
    habit = data["habit"]
    currency = data["currency"]
    symbol = get_random_stock(start_year=year)
    stock_info = get_stock_info(symbol)
    result = calculate_investment(
        start_year=year,
        daily_spend=daily_spend,
        symbol=symbol
    )
    total_invested = int(result["total_invested"])
    total_value = int(result["total_value"])
    missed_profit = int(total_value - total_invested)
    profit_percent = result["profit_percent"]
    final_text = generate_final_message(
        symbol, stock_info, habit, year, daily_spend, currency,
        total_value, total_invested, missed_profit, profit_percent
    )
    await message.answer(final_text)
    await state.clear()

def register_handlers(dp):
    dp.include_router(router) 