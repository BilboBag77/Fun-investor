import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User
from aiogram.fsm.context import FSMContext
from handlers import process_user_input, validate_with_gpt, generate_result_message

@pytest.fixture
def message():
    """Фикстура для создания тестового сообщения"""
    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 123456
    msg.text = "test message"
    return msg

@pytest.fixture
def state():
    """Фикстура для создания тестового состояния"""
    state = AsyncMock(spec=FSMContext)
    state.get_state.return_value = "InvestmentStates:year"
    return state

@pytest.mark.asyncio
async def test_process_user_input_empty_message(message, state):
    """Тест обработки пустого сообщения"""
    message.text = ""
    await process_user_input(message, state)
    state.set_state.assert_not_called()

@pytest.mark.asyncio
async def test_process_user_input_no_state(message, state):
    """Тест обработки сообщения без состояния"""
    state.get_state.return_value = None
    await process_user_input(message, state)
    state.set_state.assert_called_once()

@pytest.mark.asyncio
async def test_validate_with_gpt():
    """Тест валидации через GPT"""
    with patch('handlers.client.chat.completions.create') as mock_create:
        mock_create.return_value.choices = [
            MagicMock(message=MagicMock(content='{"is_valid": true, "reason": "", "normalized_value": "test"}'))
        ]
        result = await validate_with_gpt("year", "2020")
        assert result["is_valid"] is True
        assert result["normalized_value"] == "test"

@pytest.mark.asyncio
async def test_generate_result_message():
    """Тест генерации результата"""
    test_data = {
        "year": "2020",
        "habit": "coffee",
        "amount": "100",
        "currency": "USD"
    }
    with patch('handlers.client.chat.completions.create') as mock_create:
        mock_create.return_value.choices = [
            MagicMock(message=MagicMock(content="Test result message"))
        ]
        result = await generate_result_message(test_data)
        assert result == "Test result message" 