import logging
import logging.config
import os
import time

import telegram
from dotenv import load_dotenv

load_dotenv("app/.env")

import openai

OPENAI_TOKEN = os.environ.get("OPENAI_TOKEN")
openai.api_key = OPENAI_TOKEN


import sys

from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import whisper

from database.database import *

whisper_model = whisper.load_model("base")

CHATGPT_MODEL = os.environ.get("CHATGPT_MODEL")


def help_command_handler(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text("Type /start to register to the service")


def start_command_handler(update, context):
    """Send a message when the command /start is issued."""
    add_new_user(update.message.chat.id)
    update.message.reply_text("You are ready to go 🚀")


def echo(update, context):
    """Echo the user message."""
    telegram_id = update.message.chat.id
    message = update.message.text
    answer = generate_response(message, telegram_id)
    update.message.reply_text(answer)


def transcribe_voice_message(voice_message: str) -> str:
    """
    Transcribe voice message using Wishper model

    TODO: Use official APIs
    """
    # Use the Whisper AI API to transcribe the voice message
    result = whisper_model.transcribe(voice_message)
    return result["text"]


def handle_voice_message(update, context):
    # Get the voice message from the update
    voice_message = context.bot.get_file(update.message.voice.file_id)
    voice_message.download(f"/tmp/voice.mp3")

    # Transcribe the voice message
    text = transcribe_voice_message("/tmp/voice.mp3")

    # Answer
    telegram_id = update.message.chat.id
    answer = generate_response(text, telegram_id)
    # Send the transcribed text back to the user
    update.message.reply_text(answer)


def add_typing(update, context):
    context.bot.send_chat_action(
        chat_id=update.message.chat.id, action=telegram.ChatAction.TYPING, timeout=1
    )
    time.sleep(1)


def generate_response(question: str, telegram_id: str) -> str:
    """Generate answer using ChatGPT."""

    row = retrieve_history(telegram_id)
    prompt = create_question_prompt(row, question)

    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=prompt)
    answer = response["choices"][0]["message"]["content"]

    logging.info("Question: %s", question)
    logging.info("Got answer: %s", answer)
    update_history_user(telegram_id, question, answer)

    return answer


def error(update, context):
    """Log Errors caused by Updates."""
    logging.warning('Update "%s" ', update)
    logging.exception(context.error)


def reset(update, context):
    telegram_id = update.message.chat.id
    reset_history_user(telegram_id)


def main():
    updater = Updater(DefaultConfig.TELEGRAM_TOKEN, use_context=True)

    dp = updater.dispatcher

    # command handlers
    dp.add_handler(CommandHandler("help", help_command_handler))
    dp.add_handler(CommandHandler("start", start_command_handler))
    dp.add_handler(CommandHandler("reset", reset))

    # message handler
    dp.add_handler(MessageHandler(Filters.text, echo))
    dp.add_handler(MessageHandler(Filters.voice, handle_voice_message))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    if DefaultConfig.MODE == "webhook":
        updater.start_webhook(
            listen="0.0.0.0",
            port=int(DefaultConfig.PORT),
            url_path=DefaultConfig.TELEGRAM_TOKEN,
        )
        updater.bot.setWebhook(DefaultConfig.WEBHOOK_URL + DefaultConfig.TELEGRAM_TOKEN)

        logging.info(f"Start webhook mode on port {DefaultConfig.PORT}")
    else:
        updater.start_polling()
        logging.info(f"Start polling mode")

    updater.idle()


class DefaultConfig:
    PORT = int(os.environ.get("PORT", 3978))
    TELEGRAM_TOKEN = os.environ.get("API_TELEGRAM", "")
    MODE = os.environ.get("MODE", "polling")
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

    @staticmethod
    def init_logging():
        logging.basicConfig(
            format="%(asctime)s - %(levelname)s - %(message)s",
            level=DefaultConfig.LOG_LEVEL,
        )
        # logging.config.fileConfig('logging.conf')


if __name__ == "__main__":
    # Enable logging
    config = DefaultConfig.init_logging()

    print(config)

    main()