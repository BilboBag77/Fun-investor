import logging
from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify
from handlers import generate_final_message
from utils import get_stock_info
from calculator import calculate_investment
from waitress import serve

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Flask app for ManyChat
app = Flask(__name__)

@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.json
    year = int(data['year'])
    habit = data['habit']
    daily_spend = float(data['daily_spend'])
    currency = data['currency']
    symbol = data.get('symbol') or 'AAPL'  # Можно добавить логику выбора
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
    text = generate_final_message(
        symbol, stock_info, habit, year, daily_spend, currency,
        total_value, total_invested, missed_profit, profit_percent
    )
    return jsonify({"text": text})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    serve(app, host="0.0.0.0", port=port) 