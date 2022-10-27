import os
import logging

from gameBot.models import *
from gameBot.wordSquad import *

from telegram import Update
from telegram.ext import CallbackContext

from random import random
import re

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

def game(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    if game_session is None:
        picked_word = Word.pick_one(5)
        game_session = WordSquadGame()
        game_session.secret_word = picked_word.word
        game_session.channel_id = channel_id
        game_session.bury_treasures()
        game_session.save()
        update.message.reply_text(f'New game started: {len(game_session.secret_word)} letters. Difficulty: {picked_word.difficulty()}')
        update.message.reply_text('Synonyms: ' + (', '.join(picked_word.synonyms()) or "0 synonym found."))
        # update.message.reply_text(f'{game_session.secret_word}')
    else:
        update.message.reply_text(f'The current game has been abandoned.')
        game_session.delete()

def game_score(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    if game_session:
        update.message.reply_text(game_session.print_score())


def guess(update: Update, context: CallbackContext) -> None:
    message = update.message
    user = TgUser.find_or_create(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
    text = message.text.lower()
    logger.debug(f'guessed {text} by {user.name}')
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    logger.debug(game_session)
    if game_session and re.match(f'^[a-z]{{{len(game_session.secret_word)}}}$', text):
        if not Word.is_english(text):
            message.reply_text("Is this an English word?", reply_to_message_id=message.message_id)
            return
        new_guess = WordGuess(game_session, update.message.text, user)
        message.reply_photo(new_guess.draw(200), reply_to_message_id=message.message_id)
        if text == game_session.secret_word:
            secret_word = Word.objects.filter(word=game_session.secret_word).first()
            message.reply_text(f"You got it! Meanings of the word {secret_word}:")
            message.reply_text('\n'.join(secret_word.meanings()))
            game_session.solved = True
            game_session.add_score(user, SCORES['game'])
            game_session.save()
            message.reply_text(game_session.print_score())

def synonyms(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.current_game(channel_id)
    if game_session:
        secret_word = Word.objects.filter(word=game_session.secret_word).first()
        update.message.reply_text(','.join(secret_word.synonyms()) or "No synonyms found.")
