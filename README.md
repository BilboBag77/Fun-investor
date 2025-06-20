# Financial Habits Investment Calculator API

Этот Flask API помогает пользователям понять, сколько денег они могли бы накопить, если бы инвестировали средства, потраченные на вредные привычки, в акции. Предназначен для интеграции с ManyChat для Instagram Direct.

## Функциональность

- REST API для обработки диалогов с пользователями
- Пошаговый диалог для сбора информации о привычках и расходах
- Расчет потенциальных инвестиций в популярные акции
- Исторический анализ с учетом реальных цен акций
- Наглядное представление результатов с мотивационными сообщениями

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` в корневой директории:
```
OPENAI_API_KEY=your_openai_api_key_here
```

## Запуск

### Локально
```bash
python main.py
```

### С Gunicorn (продакшен)
```bash
gunicorn wsgi:app -b 0.0.0.0:5000
```

## API Endpoints

### POST /webhook
Основной endpoint для интеграции с ManyChat.

**Request Body:**
```json
{
  "message": {
    "text": "2020"
  },
  "user": {
    "id": "user123"
  }
}
```

**Response:**
```json
{
  "messages": [
    {
      "type": "text",
      "text": "Хорошо, спасибо за информацию. Какая вредная привычка у тебя есть?"
    }
  ]
}
```

### GET /health
Проверка состояния сервера.

### GET /
Информация об API.

## Интеграция с ManyChat

1. В ManyChat создайте External Request
2. URL: `https://your-domain.com/webhook`
3. Method: POST
4. Headers: `Content-Type: application/json`
5. Body: Передайте весь payload от пользователя

## Диалоговые состояния

1. **waiting_for_year** - ожидание года начала работы
2. **waiting_for_habits** - ожидание описания вредной привычки
3. **waiting_for_daily_cost** - ожидание ежедневных расходов
4. **waiting_for_currency** - ожидание выбора валюты
5. **waiting_for_confirmation** - ожидание подтверждения

## Технический стек

- Flask 2.3.0
- yfinance 0.2.36
- OpenAI API
- python-dotenv 1.0.0
- gunicorn (для продакшена)

## Деплой

Сервер готов к деплою на Render, Heroku или другие платформы. Убедитесь, что установлена переменная окружения `PORT`. 