import logging
import os

from dotenv import load_dotenv

from openai_helper import OpenaiHelper
from telegram_bot import TelegramBot

logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO)
    # level=logging.DEBUG)

def main():
    # Read .env file
    load_dotenv()
    # Check if the required environment variables are set
    required_values = ['TELEGRAM_BOT_TOKEN', 'OPENAI_API_KEY']
    missing_values = [value for value in required_values if os.environ.get(value) is None]
    if len(missing_values) > 0:
        logging.error(f'The following environment values are missing in your .env: {", ".join(missing_values)}')
        exit(1)

    # Setup configurations
    openai_config = {
        'api_key': os.environ['OPENAI_API_KEY'],
        'show_usage': os.environ.get('SHOW_USAGE', 'false').lower() == 'true',
        'proxy': os.environ.get('PROXY', None),

        # 'gpt-3.5-turbo' or 'gpt-3.5-turbo-0301'
        'model': 'gpt-3.5-turbo',
        # open-api ref: https://platform.openai.com/docs/api-reference/chat
        'assistant_prompt': 'You are a helpful assistant.',
        'temperature': 1,
        'max_tokens': 1200,
        'presence_penalty': 0,
        'frequency_penalty': 0,

        # The DALL·E generated image size
        'image_size': '512x512'
    }

    telegram_config = {
        'token': os.environ['TELEGRAM_BOT_TOKEN'],
        'allowed_user_ids': os.environ.get('ALLOWED_TELEGRAM_USER_IDS', '*'),
        'proxy': os.environ.get('PROXY', None)
    }


    # Setup and run ChatGPT and Telegram bot
    openai_helper = OpenaiHelper(config=openai_config)
    telegram_bot = TelegramBot(config=telegram_config, openai=openai_helper)
    telegram_bot.run()


if __name__ == '__main__':
    main()
