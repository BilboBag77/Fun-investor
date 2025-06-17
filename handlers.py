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

# Словарь с вопросами для каждого шага
QUESTIONS = {
    "year": "Привет! Я финансовый ассистент Константина. Давай начнем с того, с какого года ты начал работать и получать зарплату?",
    "habit": "Хорошо, спасибо за информацию. Следующий вопрос: какая у тебя вредная привычка, на которую ты тратишь деньги? (кофе, сигареты, фастфуд и т.д.)",
    "amount": "Сколько ты тратишь на эти вредные привычки в день?",
    "currency": "В какой валюте ты тратишь эти {amount} в день на вредные привычки?",
    "confirm": "Ты тратишь примерно {monthly_amount} {currency} в месяц. Готов откладывать такую сумму?",
    "motivate": "Готово! Вот ваш результат:"
}

# Инициализация клиента OpenAI
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CURRENCIES = ["RUB", "USD", "EUR", "AMD", "KZT", "UAH", "BYN", "GBP", "CNY"]
CONFIRM_WORDS = ["да", "готов", "ок", "согласен", "yes", "go"]

# --- START ---
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    await state.set_state(InvestmentStates.year)
    await message.answer(QUESTIONS["year"])

@router.message()
async def process_user_input(message: Message, state: FSMContext):
    """Обработчик всех пользовательских сообщений"""
    # Фильтр на пустые сообщения
    if not message.text or not message.text.strip():
        return

    current_state = await state.get_state()
    if not current_state:
        await state.set_state(InvestmentStates.year)
        await message.answer(QUESTIONS["year"])
        return

    user_input = message.text
    step = current_state.split(":")[-1]

    # Логируем входящее сообщение
    logging.info(f"User ({message.from_user.id}) [{step}]: {user_input}")
    
    # Валидируем ответ через GPT
    validation = await validate_with_gpt(step, user_input)
    logging.info(f"GPT validation: {validation}")
    
    if validation["is_valid"]:
        value = validation.get("normalized_value") or user_input
        await state.update_data(**{step: value})
        next_state = get_next_state(current_state)
        next_step = next_state.state.split(":")[-1]
        await state.set_state(next_state)
        data = await state.get_data()
        
        if next_step == "motivate":
            result = await generate_result_message(data)
            logging.info(f"Bot [motivate]: {result}")
            await state.clear()
            await message.answer(result, parse_mode="HTML")
        else:
            next_question = QUESTIONS[next_step]
            if next_step == "currency":
                next_question = next_question.format(amount=data["amount"])
            elif next_step == "confirm":
                monthly_amount = float(data["amount"]) * 30
                next_question = next_question.format(
                    monthly_amount=monthly_amount,
                    currency=data["currency"]
                )
            logging.info(f"Bot [{next_step}]: {next_question}")
            await message.answer(next_question)
    else:
        logging.info(f"Bot [clarify {step}]: {validation['reason']}")
        await message.answer(f"Пожалуйста, уточните: {validation['reason']}\n\n{QUESTIONS[step]}")

async def validate_with_gpt(step: str, user_input: str) -> dict:
    """Валидация ответа пользователя через GPT"""
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - валидатор ответов пользователя. Твоя задача - проверить, соответствует ли ответ пользователя ожидаемому формату."},
                {"role": "user", "content": f"Шаг: {step}\nОтвет пользователя: {user_input}\n\nПроверь ответ и верни JSON в формате:\n{{\"is_valid\": true/false, \"reason\": \"причина\", \"normalized_value\": \"нормализованное значение\"}}"}
            ],
            temperature=0.3
        )
        return eval(response.choices[0].message.content)
    except Exception as e:
        logging.error(f"Error in GPT validation: {e}")
        return {"is_valid": True, "reason": "", "normalized_value": user_input}

async def generate_result_message(data: dict) -> str:
    """Генерация финального мотивационного сообщения"""
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - финансовый мотиватор. Твоя задача - создать мотивационное сообщение на основе данных о вредных привычках пользователя."},
                {"role": "user", "content": f"Данные пользователя:\nГод начала работы: {data['year']}\nВредная привычка: {data['habit']}\nЕжедневные траты: {data['amount']} {data['currency']}\n\nСоздай мотивационное сообщение с расчетами потенциальных инвестиций."}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error in GPT result generation: {e}")
        return "Извините, произошла ошибка при генерации результата. Пожалуйста, попробуйте позже."

def get_next_state(current_state: str) -> InvestmentStates:
    """Получение следующего состояния"""
    states = list(InvestmentStates.__annotations__.keys())
    current_index = states.index(current_state.split(":")[-1])
    next_state_name = states[current_index + 1]
    return getattr(InvestmentStates, next_state_name)

def register_handlers(dp):
    dp.include_router(router) 