import os
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, PollHandler, PollAnswerHandler, RegexHandler, CallbackContext
from telegram import Update

from gameBot.botCommands import *
import mongoengine

mongoengine.connect(
    db=os.environ['MONGODB_DB'],
    host=os.environ['MONGODB_HOST'],
    username=os.environ['MONGODB_USERNAME'],
    password=os.environ['MONGODB_PASSWORD']
)

TOKEN = os.environ["BOT_TOKEN"]
PROD = os.environ.get("PROD", "false")
DOMAIN = os.environ.get("DOMAIN", "wordsquad.awes.one")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

def help(update: Update, context: CallbackContext) -> None:
    """Inform user about what this bot can do"""
    update.message.reply_text(
        'Use /game or /game6 to start a new game and type a word to guess.\n' +
        'In the response:\n' +
        '- Gray means wrong letter\n' +
        '- Yellow means correct letter but in wrong place\n' +
        '- Purple means correct letter in correct place\n' +
        '- Green letters at bottom are the potential ones for this game\n' +
        'Get all letters purple to win.'
    )

def debug(update: Update, context: CallbackContext) -> None:
    """Debugging function"""
    logger.info(update)
    logger.info(context)


def main() -> None:
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('help', help))
    # dispatcher.add_handler(CommandHandler('debug', debug))
    # dispatcher.add_handler(CommandHandler('users', users))
    # dispatcher.add_handler(CommandHandler('adduser', add_user))
    dispatcher.add_handler(CommandHandler('game', game))
    dispatcher.add_handler(CommandHandler('game6', game6))
    dispatcher.add_handler(CommandHandler('endgame', endgame))
    dispatcher.add_handler(CommandHandler('giveup', endgame))
    dispatcher.add_handler(CommandHandler('gamescore', game_score))
    dispatcher.add_handler(CommandHandler('stats', stats))
    dispatcher.add_handler(CommandHandler('info', info))
    dispatcher.add_handler(CommandHandler('message_dev', message_developer))
    dispatcher.add_handler(CommandHandler('leaderboard', leaderboard))
    dispatcher.add_handler(CommandHandler('leaderboardyear', leaderboard_year))
    dispatcher.add_handler(MessageHandler(Filters.text, guess, run_async=True))
    dispatcher.add_error_handler(error_handler, run_async=True)

    # Start the Bot
    if PROD == 'true':
    # enable webhook
        updater.start_webhook(listen="0.0.0.0", port=8000, url_path=TOKEN, webhook_url=f'https://{DOMAIN}/{TOKEN}')
    else:
        # enable polling
        updater.start_polling()
    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == '__main__':
    main()
