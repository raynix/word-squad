import os

from gameBot.models import *
from gameBot.wordSquad import *

from telegram import Update
from telegram.ext import CallbackContext

from random import random
import re

words5 = [ w.word for w in Word.objects.filter(word__regex = r'^[a-z]{5}$')[:100]]

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
    game_session = WordSquadGame.objects(channel_id = channel_id, solved = False).first()
    if game_session is None:
        global words5
        game_session = WordSquadGame()
        game_session.secret_word = words5[int((len(words5) - 1) * random())]
        game_session.channel_id = channel_id
        game_session.bury_treasures()
        game_session.save()
        update.message.reply_text(f'New game started: {len(game_session.secret_word)} letters.')
        # update.message.reply_text(f'{game_session.secret_word}')
    else:
        update.message.reply_text(f'Game already started.')
        game_session.delete()

def game_score(update: Update, context: CallbackContext) -> None:
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.objects(channel_id = channel_id, solved = False).first()
    if game_session is not None:
        update.message.reply_text(game_session.print_score())


def guess(update: Update, context: CallbackContext) -> None:
    user = TgUser.objects(tg_user_id=update.message.from_user.id).first()
    if user is None:
        user = TgUser(
            tg_user_id = update.message.from_user.id,
            name=f'{update.message.from_user.first_name or ""} {update.message.from_user.last_name or ""}',
        )
        user.save()

    text = update.message.text.lower()
    if not Word.is_english(text):
        update.message.reply_text("Is this an English word?", reply_to_message_id=update.message.message_id)
        return
    channel_id = update.effective_chat.id
    game_session = WordSquadGame.objects(channel_id = channel_id, solved = False).first()
    if game_session is not None and re.match(f'^[a-z]{{{len(game_session.secret_word)}}}$', text):
        new_guess = WordGuess(game_session, update.message.text, user)
        update.message.reply_photo(new_guess.draw(), reply_to_message_id=update.message.message_id)
        if text == game_session.secret_word:
            update.message.reply_text("Great guess!")
            game_session.solved = True
            game_session.add_score(user, SCORES['game'])
            game_session.save()
            update.message.reply_text(game_session.print_score())
