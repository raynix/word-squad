import logging
import traceback, html, json
import psutil
import os
import datetime, time

from gameBot.models import *
from gameBot.wordSquad import *
from gameBot.redisHelper import cache_guess, get_cached_guesses, lock

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from telegram.constants import ParseMode

from random import choice

DEVELOPER_CHAT_ID = 1262447783
WORD_NOT_FOUND = [
    "Guess it's a word but it's not in my dictionary. You can reply the word and use /suggest to add it, if you wish",
]

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

async def theme(update: Update, context: CallbackContext) -> None:
    choices = [
        [InlineKeyboardButton("dark", callback_data="theme:dark"), InlineKeyboardButton("light", callback_data="theme:light")],
    ]
    await update.message.reply_text(
        "Please select theme for this channel:",
        reply_markup=InlineKeyboardMarkup(choices)
    )

async def theme_callback(update: Update, context: CallbackContext) -> None:
    channel = TgChannel.find_or_create(update.effective_chat.id)
    query = update.callback_query
    data = query.data.split(':')
    if len(data) != 2:
        return
    theme = data[1]
    channel.theme = theme
    channel.save()
    await query.edit_message_text(f"Theme has been set to {theme}")

async def game(update: Update, context: CallbackContext) -> None:
    choices = [
        [InlineKeyboardButton("Classic: 5 letters", callback_data="game:5")],
        [InlineKeyboardButton("Advanced: 6 letters", callback_data="game:6")],
        [InlineKeyboardButton("Hardcore: 7 letters", callback_data="game:7")]
    ]
    channel = TgChannel.find_or_create(update.effective_chat.id)
    game_session = WordSquadGame.current_game(channel.tg_id)
    if game_session is None:
        if channel.games_counter == 0:
            channel.games_counter = WordSquadGame.objects(channel_id=channel.tg_id).count()
            channel.save()
        if channel.in_trial_mode():
            WordSquadGame.start(channel.tg_id, 0)
            await update.message.reply_text(f"Started in trial mode, play {10 - channel.games_counter} more games to unlock all words.")
        else:
            await update.message.reply_text(
                "Please select game mode:",
                reply_markup=InlineKeyboardMarkup(choices)
            )
    else:
        await update.message.reply_text(f'There\'s already an ongoing name: {len(game_session.secret_word)} letters. You can use /giveup to quit it.')

async def game_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data.split(':')
    if len(data) != 2:
        return
    length = data[1]
    channel = TgChannel.find_or_create(update.effective_chat.id)
    game_session = WordSquadGame.current_game(channel.tg_id)
    if game_session is None:
        game_session = WordSquadGame.start(channel.tg_id, length)
        await query.edit_message_text(
            f'New game started: {len(game_session.secret_word)} letters. Difficulty: {game_session.difficulty}\n' +
            f'Rating: {game_session.rating}\n' +
            f'Prize: {game_session.bonus_points()} points'
        )
        await query.answer("Game started, have fun!", show_alert=True)

async def endgame(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    if game_session:
        game_session.delete()
        await update.message.reply_text(f'Maybe the word "{game_session.secret_word}" is a bit too random. Please use /game to start a new one.')

async def game_score(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    if game_session:
        await update.message.reply_text(game_session.print_score())

async def guess(update: Update, context: CallbackContext) -> None:
    message = update.message
    if not message:
        return
    user = TgUser.find_or_create(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
    text = message.text.lower()
    logger.debug(f'guessed {text} by {user.name}')
    channel = TgChannel.find_or_create(update.effective_chat.id)
    with lock(f"lock_guess_{channel.tg_id}"):
        game_session = WordSquadGame.current_game(channel.tg_id)
        logger.debug(game_session)
        if game_session and text.isalpha() and len(text) == len(game_session.secret_word):
            if not Word.is_english(text):
                warning = await message.reply_text(choice(WORD_NOT_FOUND), reply_to_message_id=message.message_id)
                cache_guess(channel.tg_id, game_session.pk, warning.message_id)
                return
            new_guess = WordGuess(guess=text, by_user=user)
            game_session.add_guess(new_guess)
            photo_message = await message.reply_photo(new_guess.draw(available_letters=game_session.available_letters, theme=channel.theme, size=200), reply_to_message_id=message.message_id)
            cache_guess(channel.tg_id, game_session.pk, photo_message.message_id)
            if text == game_session.secret_word:
                await message.reply_text(
                    f"You got it! It is '{text}'!"
                )
                await message.reply_text(
                    f"For the meanings of '{text}' please see https://www.collinsdictionary.com/us/dictionary/english/{text}"
                )
                game_session.solved = True
                game_session.add_score(user, game_session.bonus_points())
                game_session.save()
                channel.games_counter += 1
                channel.save()
                await message.reply_text(game_session.print_score())
                choices = [[
                    InlineKeyboardButton("👍", callback_data=f"rating:{text}:+"),
                    InlineKeyboardButton("👎", callback_data=f"rating:{text}:-")
                ]]
                await message.reply_text(
                    "Do you like this word?",
                    reply_markup=InlineKeyboardMarkup(choices)
                )

                choices = [[
                    InlineKeyboardButton("Yes, please", callback_data=f"cleanup:{game_session.pk}:+"),
                    InlineKeyboardButton("No, keep them", callback_data=f"cleanup:{game_session.pk}:-")
                ]]
                await message.reply_text(
                    "Would you like to clean up images of this game?",
                    reply_markup=InlineKeyboardMarkup(choices)
                )

async def guess_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data.split(':')
    if len(data) != 3:
        return
    word = data[1]
    rating = data[2]
    dictWord = Word.find(word)
    if dictWord:
        if rating == '+':
            dictWord.upvote()
        else:
            dictWord.downvote()
    await query.edit_message_text("Thanks for your feedback!")

async def cleanup_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data.split(':')
    if len(data) != 3:
        return
    game_session = data[1]
    choice = data[2]
    channel_id = update.effective_chat.id
    with lock(f"lock_clean_{channel_id}"):
        if choice == '+':
            for messageId in get_cached_guesses(channel_id, game_session):
                await context.bot.delete_message(int(channel_id), int(messageId))
        await query.delete_message()

async def suggest(update: Update, context: CallbackContext) -> None:
    message = update.message or update.edited_message
    if message.reply_to_message and message.reply_to_message.text:
        suggested = message.reply_to_message.text
        if suggested.isalpha():
            if Word.is_english(suggested):
                await update.message.reply_text(f"The word '{suggested}' is already in my dictionary.")
            elif Word.ingest(suggested):
                await update.message.reply_text(f"The word '{suggested}' has been added.")
            else:
                await update.message.reply_text(f"Failed to add '{suggested}'. Not found at api.dictionaryapi.dev.")
    else:
        await message.reply_text("Please select the suggested word, reply, then use this command.")

async def synonyms(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    if game_session:
        secret_word = Word.objects.filter(word=game_session.secret_word).first()
        await update.message.reply_text(','.join(secret_word.synonyms()) or "No synonyms found.")

async def stats(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    await update.message.reply_text(
        WordSquadGame.channel_rank(channel_id) + '\n' +
        WordSquadGame.histogram()
    )

async def info(update: Update, context: CallbackContext) -> None:
    try:
        with open('/app/build-time') as f:
            build_time = f.read()
    except:
        build_time = 'Timestamp not found.'
    start_ts = psutil.Process(os.getpid()).create_time()
    current_ts = time.time()
    await update.message.reply_text(
        f'Build-time: {build_time}\n' +
        f"Uptime since deploy: {datetime.timedelta(seconds=int(current_ts-start_ts))}\n" +
        f"CPU: {psutil.cpu_percent()}%\n" +
        f"Memory: {psutil.virtual_memory().percent}%\n\n" +
        "This game bot will always be free to play. If you'd like to donate a few bucks to keep me encouraged, please go to https://patreon.com/raynix"
    )

async def leaderboard(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    await update.message.reply_text(WordSquadGame.total_points(channel_id=channel_id))

async def leaderboard_year(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    await update.message.reply_text(WordSquadGame.total_points(channel_id=channel_id, days=365))

async def hint(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    await update.message.reply_text(' '.join(game_session.available_letters).upper())

async def message_developer(update: Update, context: CallbackContext) -> None:
    """Leave a message to the developer."""
    message = update.message or update.edited_message
    if message.reply_to_message and message.reply_to_message.text:
        text = (
            f"A message was left for the developer:\n"
            f"<pre>{html.escape(message.reply_to_message.text)}</pre>"
        )

        # And send it to the developer.
        await context.bot.send_message(chat_id=DEVELOPER_CHAT_ID, text=text, parse_mode=ParseMode.HTML)
        await message.reply_text("Message left.")
    else:
        await message.reply_text("Please reply a message, then use this command. The replied message will be delivered.")

async def error_handler(update: Update, context: CallbackContext) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await context.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )
    # Unnecessary
    # await update.message.reply_text("Oops something messed up here. My master has been notified.")
