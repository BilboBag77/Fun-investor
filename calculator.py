import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

def calculate_investment(start_year: int, daily_spend: float, symbol: str, currency: str = "USD") -> dict:
    """
    Рассчитать инвестиционную доходность по заданным параметрам.
    """
    try:
        # 1. Определяем даты
        start_date = datetime(start_year, 1, 1)
        now = datetime.now()
        months = (now.year - start_date.year) * 12 + (now.month - start_date.month) + 1
        monthly_spend = daily_spend * 30

        # 2. Получаем исторические данные
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start_date.strftime("%Y-%m-%d"), end=now.strftime("%Y-%m-%d"), interval="1mo")
        
        if hist.empty:
            raise ValueError("Нет данных по активу")

        # 3. Для каждого месяца: покупаем на первое число месяца
        total_units = 0
        total_invested = 0
        monthly_returns = []
        
        for date, row in hist.iterrows():
            price = row['Close']
            units = monthly_spend / price
            total_units += units
            total_invested += monthly_spend
            monthly_returns.append((price / hist['Close'].iloc[0]) - 1)

        # 4. Текущая цена и расчеты
        current_price = hist['Close'].iloc[-1]
        total_value = total_units * current_price
        
        # Расчет дополнительных метрик
        years = months / 12
        cagr = (total_value / total_invested) ** (1 / years) - 1 if total_invested > 0 else 0
        volatility = np.std(monthly_returns) * np.sqrt(12) if len(monthly_returns) > 1 else 0
        sharpe_ratio = (cagr - 0.02) / volatility if volatility > 0 else 0  # Assuming 2% risk-free rate
        
        profit_percent = ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0

        return {
            "months": months,
            "total_invested": total_invested,
            "total_units": total_units,
            "current_price": current_price,
            "total_value": total_value,
            "profit_percent": profit_percent,
            "cagr": cagr * 100,  # Convert to percentage
            "volatility": volatility * 100,  # Convert to percentage
            "sharpe_ratio": sharpe_ratio,
            "fallback": False
        }
    except Exception as e:
        # Fallback: используем CAGR (реальную среднегодовую доходность)
        now = datetime.now()
        start_date = datetime(start_year, 1, 1)
        months = (now.year - start_date.year) * 12 + (now.month - start_date.month) + 1
        monthly_spend = daily_spend * 30
        total_invested = months * monthly_spend
        years = months / 12

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date.strftime("%Y-%m-%d"), end=now.strftime("%Y-%m-%d"))
            
            if hist.empty or len(hist['Close']) < 2:
                raise ValueError("Недостаточно данных для расчета")

            price_start = hist['Close'].iloc[0]
            price_end = hist['Close'].iloc[-1]
            cagr = (price_end / price_start) ** (1 / years) - 1
            
            # Считаем итоговую сумму с реальной средней доходностью
            total_value = total_invested * ((1 + cagr) ** years)
            profit_percent = ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
            
            return {
                "months": months,
                "total_invested": total_invested,
                "total_units": None,
                "current_price": price_end,
                "total_value": total_value,
                "profit_percent": profit_percent,
                "cagr": cagr * 100,
                "volatility": None,
                "sharpe_ratio": None,
                "fallback": True,
                "error": str(e)
            }
        except Exception as e:
            return {
                "months": months,
                "total_invested": total_invested,
                "total_units": None,
                "current_price": None,
                "total_value": None,
                "profit_percent": None,
                "cagr": None,
                "volatility": None,
                "sharpe_ratio": None,
                "fallback": True,
                "error": str(e)
            } 