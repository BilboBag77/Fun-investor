import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(bot)

async def main():
    # Register handlers
    from handlers import register_handlers
    register_handlers(dp)
    
    # Start polling
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main()) 