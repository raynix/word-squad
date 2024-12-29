import os
import logging
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, CallbackContext, MessageHandler
from telegram.ext import filters
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from gameBot.botCommands import *
import mongoengine

mongoengine.connect(
    db=os.environ.get('MONGODB_DB', 'wordsquad'),
    host=os.environ.get('MONGODB_HOST', 'localhost'),
    username=os.environ.get('MONGODB_USERNAME', 'root'),
    password=os.environ.get('MONGODB_PASSWORD', 'pass'),
)

TOKEN = os.environ["BOT_TOKEN"]
PROD = os.environ.get("PROD", "false")
DOMAIN = os.environ.get("DOMAIN", "wordsquad.awes.one")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inform user about what this bot can do"""
    await update.message.reply_text(
        'Use /game to start a new game and type a word to guess.\n' +
        'In the response:\n' +
        '- Gray means wrong letter\n' +
        '- Yellow means correct letter but in wrong place\n' +
        '- Purple means correct letter in correct place\n' +
        '- Green letters at bottom are the potential ones for this game\n' +
        'Get all letters purple to win.\n\n' +
        'Use /fof to start a Friend or Foe game, you will see random synonyms and antonyms\n' +
        'as clues to guess the secret word. Letters will be revealed after a few guesses, \n' +
        'but bonus points will be reduced too.'
    )

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debugging function"""
    logger.info(update)
    logger.info(context)

# async def test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     pass

def main() -> None:
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('help', help))
    # application.add_handler(CommandHandler('debug', debug))
    # application.add_handler(CommandHandler('test', test))
    application.add_handler(CommandHandler('game', game))
    application.add_handler(CommandHandler('fof', fof_game))
    application.add_handler(CallbackQueryHandler(game_callback, pattern='^game:[-0-9]+$'))
    application.add_handler(CommandHandler('endgame', endgame))
    application.add_handler(CommandHandler('giveup', endgame))
    application.add_handler(CommandHandler('gamescore', game_score))
    application.add_handler(CommandHandler('info', info))
    application.add_handler(CommandHandler('message_dev', message_developer))
    application.add_handler(CommandHandler('leaderboard', leaderboard))
    application.add_handler(CommandHandler('leaderboardyear', leaderboard_year))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('suggest', suggest))
    application.add_handler(CommandHandler('theme', theme))
    application.add_handler(CommandHandler('push_announcement', push_announcement))
    application.add_handler(CallbackQueryHandler(theme_callback, pattern='^theme:.*$'))
    application.add_handler(CallbackQueryHandler(guess_callback, pattern='^rating:.*$'))
    application.add_handler(CallbackQueryHandler(cleanup_callback, pattern='^cleanup:.*$'))
    application.add_handler(MessageHandler(filters.TEXT, guess, block=False))
    application.add_error_handler(error_handler, block=False)

    # Start the Bot
    if PROD == 'true':
        # enable webhook
        application.run_webhook(listen="0.0.0.0", port=8000, url_path=TOKEN, webhook_url=f'https://{DOMAIN}/{TOKEN}')
    else:
        # enable polling
        application.run_polling()
    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT

if __name__ == '__main__':
    main()
