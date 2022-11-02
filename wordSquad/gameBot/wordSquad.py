from email.policy import default
from random import random
from PIL import Image, ImageDraw, ImageFont
from tempfile import SpooledTemporaryFile
from mongoengine import Document, EmbeddedDocument, fields

import re
import datetime

from gameBot.models import TgUser

CORRECT_LETTER = 2
MISPLACE_LETTER = 1
WRONG_LETTER = 0

SCORES = {
    'accurate': 10,
    'splash': 5,
    'game': 20
}

FONT_COLORS = [
    (168,168,168),
    (10,10,10),
    (10,10,10)
]

FILL_COLORS = [
    (225,225,225),
    (220,220,60),
    (151, 23, 255)
]

class WordGuess(EmbeddedDocument):
    guess = fields.StringField()
    letter_results = fields.ListField(default=[])
    by_user = fields.ReferenceField(TgUser)

    def draw(self, size=100):
        with SpooledTemporaryFile() as in_memory_file:
            img = Image.new('RGB', (size*len(self.guess), 2 * size), color = (240,240,240))
            font = ImageFont.truetype("nk57-monospace-no-rg.ttf", int(size * 0.9))
            draw = ImageDraw.Draw(img)
            for idx, correctness in enumerate(self.letter_results):
                draw.rectangle([int(size * (0.05 + idx)), int(size * 0.05), int(size * (idx + 0.9)) , int(size * 0.95)], outline='grey', width=3, fill=FILL_COLORS[correctness])
                if correctness == MISPLACE_LETTER:
                    draw.rectangle([int(size * (0.15 + idx)), int(size * 0.15), int(size * (idx + 0.8)), int(size * 0.85)], fill=FILL_COLORS[0])
                draw.text((int(size * (0.15 + idx)), 0), self.guess[idx].upper(), font=font, fill=FONT_COLORS[correctness])
            img.save(in_memory_file, 'png')
            in_memory_file.seek(0)
            png_data = in_memory_file.read()
            return png_data


class WordSquadGame(Document):
    channel_id = fields.IntField()
    secret_word = fields.StringField()
    solved = fields.BooleanField(default=False)
    treasures = fields.ListField(default = [])
    scores = fields.DictField(default = {})
    created_at = fields.DateTimeField(default=datetime.datetime.utcnow)
    guesses = fields.EmbeddedDocumentListField(WordGuess)

    def __str__(self):
        return f'{self.channel_id}:{self.secret_word}:{self.solved}'

    def add_guess(self, guess) -> None:
        for idx, letter in enumerate(guess.guess):
            # letter guessed accurately
            result = WRONG_LETTER
            if letter == self.secret_word[idx]:
                result = CORRECT_LETTER
                self.claim_treasure('accurate', guess.by_user, idx)
            # letter guessed but in wrong location
            elif letter in self.secret_word:
                result = MISPLACE_LETTER
                self.claim_treasure('splash', guess.by_user, idx)
            guess.letter_results.append(result)
        self.guesses.append(guess)
        self.save()

    def claim_treasure(self, claim_type, user, treasure_idx):
        if claim_type == 'accurate' and self.treasures[treasure_idx][claim_type] is None:
            self.treasures[treasure_idx][claim_type] = user
            self.add_score(user, SCORES[claim_type])
        elif self.treasures[treasure_idx]['accurate'] is None and self.treasures[treasure_idx][claim_type] is None:
            self.treasures[treasure_idx][claim_type] = user
            self.add_score(user, SCORES[claim_type])

    def add_score(self, user, score):
        if user.name in self.scores.keys():
            self.scores[user.name] += score
        else:
            self.scores[user.name] = score

    def bury_treasures(self):
        if self.secret_word:
            for idx, v in enumerate(self.secret_word):
                self.treasures.append({
                    'letter': v,
                    'splash': None,
                    'accurate': None
                })
    def print_score(self):
        return (
            'Game scores: \n' +
            '\n'.join([f'{k}: {v}' for k, v in sorted(self.scores.items(), key=lambda item: item[1], reverse=True)])
        )

    @classmethod
    def current_game(cls, channel_id):
        return cls.objects(channel_id = channel_id, solved = False).first()

    @classmethod
    def total_games(cls, channel_id=None):
        if channel_id:
            return cls.objects.filter(channel_id=channel_id).count()
        else:
            return cls.objects.count()

    @classmethod
    def total_points(cls, channel_id):
        records = {}
        for game in WordSquadGame.objects(channel_id=channel_id, solved=True).all():
            for k, v in game.scores.items():
                if k in records.keys():
                    records[k] += v
                else:
                    records[k] = v
        return (
           'Leaderboard of this channel:\n' +
            '\n'.join([f'{k}: {v}' for k, v in sorted(records.items(), key=lambda item: item[1], reverse=True)])
        )
