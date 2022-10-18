import os

from gameBot.models import *
from gameBot.wordSquad import *

from telegram import Update
from telegram.ext import CallbackContext

from random import random
import re



game_session = None

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
    global game_session
    if game_session is None:
        game_session = WordSquadGame()
        update.message.reply_text(f'New word: {game_session.secret_word}')
    else:
        for guess in game_session.guesses:
            update.message.reply_photo(guess.draw())


def guess(update: Update, context: CallbackContext) -> None:
    text = update.message.text.lower()
    if game_session and re.match(f'^[a-z]{{{len(game_session.secret_word)}}}$', text):
        new_guess = WordGuess(game_session.secret_word, update.message.text)
        update.message.reply_photo(new_guess.draw())
