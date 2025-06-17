import os
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from states import InvestmentStates
from utils import get_random_stock
from calculator import calculate_investment
from openai import AsyncOpenAI
from datetime import datetime

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
    await message.answer("С какого года ты работаешь?")

# --- YEAR ---
@router.message(InvestmentStates.waiting_for_year)
async def process_year(message: Message, state: FSMContext):
    year = message.text.strip()
    if not (year.isdigit() and 1970 <= int(year) <= datetime.now().year):
        await message.answer(f"Пожалуйста, укажи год цифрами от 1970 до {datetime.now().year}")
        return
    await state.update_data(year=int(year))
    await state.set_state(InvestmentStates.waiting_for_habits)
    await message.answer("Какие вредные привычки у тебя есть?")

# --- HABITS ---
@router.message(InvestmentStates.waiting_for_habits)
async def process_habits(message: Message, state: FSMContext):
    habit = message.text.strip()
    if len(habit) < 2:
        await message.answer("Опиши привычку чуть подробнее!")
        return
    await state.update_data(habit=habit)
    await state.set_state(InvestmentStates.waiting_for_daily_cost)
    await message.answer("Сколько это стоит в день?")

# --- DAILY COST ---
@router.message(InvestmentStates.waiting_for_daily_cost)
async def process_daily_cost(message: Message, state: FSMContext):
    try:
        daily_spend = float(message.text.replace(",", ".").replace(" ", ""))
        if daily_spend <= 0:
            raise ValueError
    except Exception:
        await message.answer("Пожалуйста, укажи сумму в день (например: 500)")
        return
    await state.update_data(daily_spend=daily_spend)
    await state.set_state(InvestmentStates.waiting_for_currency)
    await message.answer(f"В какой валюте ты тратишь эти деньги? ({', '.join(CURRENCIES)})")

# --- CURRENCY ---
@router.message(InvestmentStates.waiting_for_currency)
async def process_currency(message: Message, state: FSMContext):
    currency = message.text.strip().upper()
    if currency not in CURRENCIES:
        await message.answer(f"Пожалуйста, выбери валюту из списка: {', '.join(CURRENCIES)}")
        return
    await state.update_data(currency=currency)
    data = await state.get_data()
    monthly = int(data["daily_spend"] * 30)
    await state.set_state(InvestmentStates.waiting_for_confirmation)
    await message.answer(f"Ты тратишь примерно {monthly} {currency} в месяц. Готов откладывать такую сумму?")

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
    result = calculate_investment(
        start_year=year,
        daily_spend=daily_spend,
        symbol=symbol
    )
    total_invested = int(result["total_invested"])
    total_value = int(result["total_value"])
    missed_profit = int(total_value - total_invested)
    profit_percent = result["profit_percent"]
    cagr = result["cagr"]
    volatility = result["volatility"] if result["volatility"] is not None else 0
    # Формируем prompt для OpenAI
    prompt = RESULT_PROMPT.format(
        year=year,
        daily_spend=daily_spend,
        currency=currency,
        habit=habit,
        symbol=symbol,
        total_value=total_value,
        total_invested=total_invested,
        missed_profit=missed_profit,
        profit_percent=profit_percent,
        cagr=cagr,
        volatility=volatility
    )
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            max_tokens=350,
            temperature=0.5
        )
        bot_reply = response.choices[0].message.content.strip()
        # Сначала call to action с годом, затем дисклеймер
        bot_reply += f"\n\nЕсли хочешь быть умнее, чем ты был в {year} — углубись в инвестиции, следи за моим инстаграмом!"
        bot_reply += "\n*Все цифры примерные, расчёт основан только на динамике актива, без учёта валютных колебаний.*"
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        bot_reply = (
            f"Если бы ты инвестировал {daily_spend} {currency} в месяц с {year} года в {symbol}, "
            f"у тебя было бы {total_value:,} {currency}. Всего потрачено: {total_invested:,} {currency}. "
            f"Упущенная выгода: {missed_profit:,} {currency}. (Ошибка генерации мотивации)\n"
            f"Если хочешь быть умнее, чем ты был в {year} — углубись в инвестиции, следи за моим инстаграмом!\n"
            f"*Все цифры примерные, расчёт основан только на динамике актива, без учёта валютных колебаний.*"
        )
    await message.answer(bot_reply)
    await state.clear()

def register_handlers(dp):
    dp.include_router(router) 