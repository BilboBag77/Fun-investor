from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from dotenv import load_dotenv
from utils import get_random_stock, words_to_number, get_stock_info, format_currency
from calculator import calculate_investment
from openai import OpenAI
from datetime import datetime
import re

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# Constants
CURRENCIES = ["RUB", "USD", "EUR", "AMD", "KZT", "UAH", "BYN", "GBP", "CNY"]
CONFIRM_WORDS = ["да", "готов", "ок", "согласен", "yes", "go"]

# User sessions storage (in production use Redis or database)
user_sessions = {}

def generate_final_message(symbol, stock_info, habit, year, daily_spend, currency, total_value, total_invested, missed_profit, profit_percent):
    """Generate final motivational message"""
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

def process_user_input(user_id, message_text):
    """Process user input and return appropriate response"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {"state": "waiting_for_year"}
    
    session = user_sessions[user_id]
    state = session["state"]
    
    if state == "waiting_for_year":
        year_match = re.search(r"\d{4}", message_text)
        if year_match:
            year = int(year_match.group())
            if 1970 <= year <= datetime.now().year:
                session["year"] = year
                session["state"] = "waiting_for_habits"
                return "Хорошо, спасибо за информацию. Какая вредная привычка у тебя есть?"
        
        return f"Пожалуйста, укажи год цифрами от 1970 до {datetime.now().year}"
    
    elif state == "waiting_for_habits":
        habit = message_text.strip().lower()
        if len(habit) < 2 or habit in ["нет", "-"] or habit.isdigit():
            return "Опиши привычку чуть подробнее!"
        
        session["habit"] = habit
        session["state"] = "waiting_for_daily_cost"
        return "Сколько примерно ты тратишь на эту вредную привычку в день?"
    
    elif state == "waiting_for_daily_cost":
        text = message_text.lower().replace(",", ".")
        match = re.search(r"[\d.]+", text)
        daily_spend = None
        if match:
            try:
                daily_spend = float(match.group())
            except Exception:
                pass
        
        if daily_spend is None:
            daily_spend = words_to_number(text)
        
        if not daily_spend or daily_spend <= 0:
            return "Пожалуйста, укажи сумму в день (например: 500 или пятьсот)"
        
        session["daily_spend"] = daily_spend
        session["state"] = "waiting_for_currency"
        return "В какой валюте ты тратишь эти деньги?"
    
    elif state == "waiting_for_currency":
        text = message_text.strip().lower()
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
            return "Пожалуйста, выбери валюту из списка: USD, EUR, RUB, AMD, KZT, UAH, BYN, GBP, CNY"
        
        session["currency"] = currency_code
        monthly = int(session["daily_spend"] * 30)
        session["state"] = "waiting_for_confirmation"
        return f"Ты тратишь примерно {monthly} {currency_code} в месяц. Готов откладывать такую сумму?"
    
    elif state == "waiting_for_confirmation":
        text = message_text.strip().lower()
        if not any(word in text for word in CONFIRM_WORDS):
            return "Если готов — напиши 'да', 'готов', 'ок' или предложи свою сумму!"
        
        # Calculate investment
        year = session["year"]
        daily_spend = session["daily_spend"]
        habit = session["habit"]
        currency = session["currency"]
        
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
        
        # Clear session
        del user_sessions[user_id]
        
        return final_text

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle ManyChat webhook requests"""
    try:
        data = request.get_json()
        
        # Extract user message and ID from ManyChat payload
        # Adjust these fields based on your ManyChat configuration
        user_message = data.get('message', {}).get('text', '')
        user_id = data.get('user', {}).get('id', '')
        
        if not user_message or not user_id:
            return jsonify({"error": "Missing message or user ID"}), 400
        
        # Process the message
        response_text = process_user_input(user_id, user_message)
        
        # Return response for ManyChat
        return jsonify({
            "messages": [
                {
                    "type": "text",
                    "text": response_text
                }
            ]
        })
        
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@app.route('/', methods=['GET'])
def home():
    """Home endpoint"""
    return jsonify({
        "message": "Financial Assistant API",
        "status": "running",
        "endpoints": {
            "webhook": "/webhook (POST)",
            "health": "/health (GET)"
        }
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 