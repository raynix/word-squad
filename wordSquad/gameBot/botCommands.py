from ast import Call
import os
import subprocess
import logging
import traceback, html, json

from gameBot.models import *
from gameBot.wordSquad import *

from telegram import Update, ParseMode
from telegram.ext import CallbackContext

from random import choice
import re

DEVELOPER_CHAT_ID = 1262447783
WORD_NOT_FOUND = [
    "Is this an English word?",
    "Guess it's a word but sorry it's not in my dictionary.",
    "Nice try mate but no.",
    "You might find better luck if you try something else.",
]

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

def users(update: Update, context: CallbackContext) -> None:
    users = TgUser.objects.all()
    if len(users) == 0:
        update.message.reply_text("No users have been added yet.")
    else:
        update.message.reply_text(
            'Available users:\n'
            + '\n'.join(f'{user.name} - {user.address}' for user in users)
        )

def add_user(update: Update, context: CallbackContext) -> None:
    error_message = "A user name is required. eg. /adduser johny."
    if len(context.args) == 0:
        update.message.reply_text(error_message)
    else:
        new_user = TgUser(name=context.args[0])
        new_user.save()
        update.message.reply_text(f'New user: {new_user.name} has been created.')

def game(update: Update, context: CallbackContext, length=5) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    if game_session is None:
        picked_word = Word.pick_one(length)
        game_session = WordSquadGame()
        game_session.secret_word = picked_word.word.lower()
        game_session.difficulty = picked_word.difficulty()
        game_session.channel_id = channel_id
        game_session.bury_treasures()
        game_session.save()
        update.message.reply_text(
            f'New game started: {len(game_session.secret_word)} letters. Difficulty: {game_session.difficulty}\n' +
            f'Prize: {game_session.bonus_points()} points'
        )
    else:
        update.message.reply_text(f'There\'s already an ongoing name: {len(game_session.secret_word)} letters.')

def game6(update: Update, context: CallbackContext) -> None:
    game(update, context, 6)

def endgame(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    if game_session:
        game_session.delete()
        update.message.reply_text(f'Maybe the word "{game_session.secret_word}" is a bit too random. Please use /game to start a new one.')

def game_score(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    if game_session:
        update.message.reply_text(game_session.print_score())

def guess(update: Update, context: CallbackContext) -> None:
    message = update.message
    if not message:
        return
    user = TgUser.find_or_create(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
    text = message.text.lower()
    logger.debug(f'guessed {text} by {user.name}')
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    logger.debug(game_session)
    if game_session and re.match(f'^[a-z]{{{len(game_session.secret_word)}}}$', text):
        if not Word.is_english(text):
            message.reply_text(choice(WORD_NOT_FOUND), reply_to_message_id=message.message_id)
            return
        new_guess = WordGuess(guess=text, by_user=user)
        game_session.add_guess(new_guess)
        message.reply_photo(new_guess.draw(available_letters=game_session.available_letters, size=200), reply_to_message_id=message.message_id)
        if text == game_session.secret_word:
            secret_word = Word.objects.filter(word__iexact=game_session.secret_word).first()
            message.reply_text(
                f"You got it! Meanings of the word {secret_word}:\n" +
                '\n'.join(secret_word.meanings())
            )
            game_session.solved = True
            game_session.add_score(user, game_session.bonus_points())
            game_session.save()
            message.reply_text(game_session.print_score())

def synonyms(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    if game_session:
        secret_word = Word.objects.filter(word=game_session.secret_word).first()
        update.message.reply_text(','.join(secret_word.synonyms()) or "No synonyms found.")

def stats(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    update.message.reply_text(
        f'Total games recorded: {WordSquadGame.total_games()}\n' +
        f'Total games in this channel: {WordSquadGame.total_games(channel_id)}'
    )

def info(update: Update, context: CallbackContext) -> None:
    try:
        with open('/app/build-time') as f:
            build_time = f.read()
    except:
        build_time = 'Timestamp not found.'
    output = subprocess.run(['uptime'], stdout=subprocess.PIPE)
    update.message.reply_text(
        f'Build-time: {build_time}\n' +
        f"Uptime: {output.stdout.decode('utf-8')}"
    )

def leaderboard(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    update.message.reply_text(WordSquadGame.total_points(channel_id=channel_id))

def hint(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    update.message.reply_text(' '.join(game_session.available_letters).upper())

def error_handler(update: Update, context: CallbackContext) -> None:
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
    context.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )
    update.message.reply_text("Oops something messed up here. My master has been notified.")
