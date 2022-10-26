from random import random
from PIL import Image, ImageDraw, ImageFont
from tempfile import SpooledTemporaryFile
from mongoengine import Document, fields

import re

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
    (60,60,60),
    (10,10,10)
]

FILL_COLORS = [
    (225,225,225),
    (220,220,60),
    (60,250,60)
]

class WordGuess:

    def __init__(self, game_session, guess, user) -> None:
        self.guess = guess
        self.results = {}
        for idx, letter in enumerate(guess):
            # letter guessed accurately
            if letter == game_session.secret_word[idx]:
                self.results[idx] = CORRECT_LETTER
                game_session.claim_treasure('accurate', user, idx)
            # letter guessed but in wrong location
            elif letter in game_session.secret_word:
                self.results[idx] = MISPLACE_LETTER
                game_session.claim_treasure('splash', user, idx)
            else:
                self.results[idx] = WRONG_LETTER

    def draw(self, size=100):
        with SpooledTemporaryFile() as in_memory_file:
            img = Image.new('RGB', (size*len(self.guess), size), color = (240,240,240))
            font = ImageFont.truetype("nk57-monospace-no-rg.ttf", int(size * 0.9))
            draw = ImageDraw.Draw(img)
            for idx, correctness in self.results.items():
                draw.rectangle([int(size * (0.05 + idx)), int(size * 0.05), int(size * (idx + 0.9)) , int(size * 0.95)], outline='grey', width=3, fill=FILL_COLORS[correctness])
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

    def __str__(self):
        return f'{self.channel_id}:{self.secret_word}:{self.solved}'

    def claim_treasure(self, claim_type, user, treasure_idx):
        if claim_type == 'accurate' and self.treasures[treasure_idx][claim_type] is None:
            self.treasures[treasure_idx][claim_type] = user
            self.add_score(user, SCORES[claim_type])
        elif self.treasures[treasure_idx]['accurate'] is None and self.treasures[treasure_idx][claim_type] is None:
            self.treasures[treasure_idx][claim_type] = user
            self.add_score(user, SCORES[claim_type])
        self.save()

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
        return 'Game scores: \n' + '\n'.join([f'{k}: {v}' for k, v in self.scores.items()])

    @classmethod
    def current_game(cls, channel_id):
        return cls.objects(channel_id = channel_id, solved = False).first()
