from email.policy import default
from random import random
from PIL import Image, ImageDraw, ImageFont
from tempfile import SpooledTemporaryFile
from mongoengine import Document, EmbeddedDocument, fields

import re
import datetime
import string
import logging

from gameBot.models import TgUser

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

CORRECT_LETTER = 2
MISPLACE_LETTER = 1
WRONG_LETTER = 0

SCORES = {
    'accurate': 10,
    'splash': 5,
    'game': 20
}

FONT_COLORS = [
    (168, 168, 168),
    (10, 10, 10),
    (10, 10, 10),
    (158, 219, 123)
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

    def wrong_letters(self):
        return [x for i, x in enumerate(self.guess) if self.letter_results[i] == 0]

    def correct_letters(self):
        return [x for i, x in enumerate(self.guess) if self.letter_results[i] > 0]

    def draw(self, available_letters, size=100):
        with SpooledTemporaryFile() as in_memory_file:
            img = Image.new('RGB', (size*len(self.guess), 2 * size), color = (240,240,240))
            font = ImageFont.truetype("nk57-monospace-no-rg.ttf", int(size * 0.9))
            draw = ImageDraw.Draw(img)
            # main letters
            for idx, correctness in enumerate(self.letter_results):
                draw.rectangle([int(size * (0.05 + idx)), int(size * 0.07), int(size * (idx + 0.9)) , int(size * 0.97)], outline='grey', width=3, fill=FILL_COLORS[correctness])
                if correctness == MISPLACE_LETTER:
                    draw.rectangle([int(size * (0.15 + idx)), int(size * 0.15), int(size * (idx + 0.8)), int(size * 0.85)], fill=FILL_COLORS[0])
                draw.text((int(size * (0.15 + idx)), 0), self.guess[idx].upper(), font=font, fill=FONT_COLORS[correctness])
            # available letters
            font = ImageFont.truetype("nk57-monospace-no-rg.ttf", int(size * 0.25))
            draw.text((int(size * 0.01), int(size * 1.1)), f'[ {"".join(available_letters).upper()} ]', font=font, fill=FONT_COLORS[3])

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
    available_letters = fields.ListField(default=list(string.ascii_lowercase))

    def __str__(self):
        return f'{self.channel_id}:{self.secret_word}:{self.solved}'

    def add_guess(self, guess) -> None:
        targets = {}
        for idx, letter in enumerate(self.secret_word):
            targets[idx] = { 'letter': letter, 'hit': False }
        sources = {}
        for idx, letter in enumerate(guess.guess):
            sources[idx] = { 'letter': letter, 'hit': False }

        guess.letter_results = [WRONG_LETTER for i in range(len(self.secret_word))]
        # letter guessed accurately
        for k, v in sources.items():
            if v['letter'] == targets[k]['letter']:
                guess.letter_results[k] = CORRECT_LETTER
                self.claim_treasure('accurate', guess.by_user, k)
                v['hit'] = True
                targets[k]['hit'] = True
        # letter guessed but in wrong location
        for i, j in sources.items():
            if j['hit']:
                continue
            for k, v in targets.items():
                if v['hit']:
                    continue
                if j['letter'] == v['letter']:
                    guess.letter_results[i] = MISPLACE_LETTER
                    self.claim_treasure('splash', guess.by_user, i)
                    v['hit'] = True
                    break
        self.guesses.append(guess)
        self.available_letters = [x for x in self.available_letters if x in guess.correct_letters() or x not in guess.wrong_letters()]
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
