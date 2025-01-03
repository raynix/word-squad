from PIL import Image, ImageDraw, ImageFont
from tempfile import SpooledTemporaryFile
from mongoengine import Document, EmbeddedDocument, fields
from math import log2

import datetime
import string
import logging
import random

from gameBot.models import TgUser, Word
from gameBot.redisHelper import redis_cached
from gameBot.themes import get_theme


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

def top_players(scores_dict, n=20):
    # scores_dict = { 'player1': 100, 'player2': 200, ... }
    sorted_list = sorted(scores_dict.items(), key=lambda item: item[1], reverse=True)[:n]
    return '\n'.join([f'{idx+1} - {item[0]}: {item[1]}' for idx, item in enumerate(sorted_list)])

class WordGuess(EmbeddedDocument):
    guess = fields.StringField()
    letter_results = fields.ListField(default=[])
    by_user = fields.ReferenceField(TgUser)

    def wrong_letters(self):
        return [x for i, x in enumerate(self.guess) if self.letter_results[i] == 0]

    def correct_letters(self):
        return [x for i, x in enumerate(self.guess) if self.letter_results[i] > 0]

    def draw(self, available_letters, theme, size=100):
        with SpooledTemporaryFile() as in_memory_file:
            length = len(self.guess)
            img = Image.new('RGB', (size * length, int(size * length * 0.4)), color = get_theme(theme)['bg'])
            font = ImageFont.truetype("nk57-monospace-no-rg.ttf", int(size * 0.9))
            draw = ImageDraw.Draw(img)
            # main letters
            for idx, correctness in enumerate(self.letter_results):
                draw.rectangle([int(size * (0.05 + idx)), int(size * 0.07), int(size * (idx + 0.9)) , int(size * 0.97)], outline='grey', width=3, fill=get_theme(theme)['fill_colors'][correctness])
                if correctness == MISPLACE_LETTER:
                    draw.rectangle([int(size * (0.12 + idx)), int(size * 0.12), int(size * (idx + 0.84)), int(size * 0.9)], fill=get_theme(theme)['fill_colors'][0])
                draw.text((int(size * (0.15 + idx)), 0), self.guess[idx].upper(), font=font, fill=get_theme(theme)['font_colors'][correctness])
            # available letters
            font = ImageFont.truetype("nk57-monospace-no-rg.ttf", int(size * 0.25))
            draw.text((int(size * 0.01), int(size * 1.1)), f'[ {"".join(available_letters).upper()} ]', font=font, fill=get_theme(theme)['font_colors'][3])

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
    difficulty = fields.StringField(default='Normal')
    rating = ''

    meta = {
        'indexes': ['channel_id', 'solved', 'created_at']
    }

    bonus = {
        'Easy': 1,
        'Normal': 2,
        'Hard': 4,
        'Very Hard': 10,
        'Ultra Hard': 20
    }

    def __str__(self):
        return f'{self.channel_id}:{self.secret_word}:{self.solved}'

    def bonus_points(self):
        return self.bonus[self.difficulty] * len(self.secret_word)

    def add_guess(self, guess) -> None:
        length = len(self.secret_word)
        guess_letters_linked = [ False for i in range(length)]
        secret_letters_linked = [ False for i in range(length)]
        guess.letter_results = [WRONG_LETTER for i in range(length)]
        # letter guessed accurately
        for idx, letter in enumerate(guess.guess):
            if letter == self.secret_word[idx]:
                guess.letter_results[idx] = CORRECT_LETTER
                self.claim_treasure('accurate', guess.by_user, idx)
                guess_letters_linked[idx] = True
                secret_letters_linked[idx] = True
        # letter guessed but in wrong location
        for idx, letter in enumerate(guess.guess):
            if guess_letters_linked[idx]:
                continue
            for idx2, letter2 in enumerate(self.secret_word):
                if secret_letters_linked[idx2]:
                    continue
                if letter == letter2:
                    guess.letter_results[idx] = MISPLACE_LETTER
                    self.claim_treasure('splash', guess.by_user, idx2)
                    secret_letters_linked[idx2] = True
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
            top_players(self.scores)
        )

    @classmethod
    def start(cls, channel_id, length: str):
        if length == 'trial':
            picked_word = Word.pick_trial()
        else:
            picked_word = Word.pick_one(length)
        game_session = WordSquadGame()
        game_session.secret_word = picked_word.word.lower()
        game_session.difficulty = picked_word.difficulty()
        game_session.rating = picked_word.rating()
        game_session.channel_id = channel_id
        game_session.bury_treasures()
        game_session.save()
        return game_session

    @classmethod
    def total_games(cls, channel_id=None):
        if channel_id:
            return cls.objects.filter(channel_id=channel_id).count()
        else:
            return cls.objects.count()

    @classmethod
    @redis_cached
    def total_points(cls, channel_id, days=30):
        from_date = datetime.datetime.today() - datetime.timedelta(days)
        records = {}
        for game in WordSquadGame.objects(channel_id=channel_id, solved=True, created_at__gte=from_date).all():
            for k, v in game.scores.items():
                if k in records.keys():
                    records[k] += v
                else:
                    records[k] = v
        return (
            f'GS Leaderboard({days} days) of this channel:\n' +
            top_players(records)
        )

    @classmethod
    @redis_cached
    def histogram(cls, days=7):
        from_date = datetime.datetime.today() - datetime.timedelta(days=days)
        pipeline = [
            {
                "$match": { "created_at": { "$gte": from_date}}
            },
            {
                "$group": {
                    "_id": { "$dateToString": { "format": "%Y-%m-%d", "date": "$created_at" }},
                    "count": { "$sum": 1 }
                }
            },
            {
                "$sort": { "_id": 1 }
            }
        ]
        return (
            f"Number of games in the past {days} days:\n" +
            "\n".join([ f"{row['_id']}: {row['count']}" for row in cls.objects.aggregate(pipeline)])
        )

    @classmethod
    @redis_cached
    def active_channels(cls, days=7):
        from_date = datetime.datetime.today() - datetime.timedelta(days=days)
        pipeline = [
            {
                "$match": { "created_at": { "$gte": from_date}}
            },
            {
                "$group": {
                    "_id": "$channel_id",
                    "count": { "$sum": 1}
                }
            },
            {
                "$sort": { "count": -1 }
            }
        ]
        return (
            f"Active channels in the past {days} days:\n" +
            "\n".join([ f"{row['_id']}: {row['count']}" for row in cls.objects.aggregate(pipeline)])
        )

    @classmethod
    @redis_cached
    def channel_rank(cls, channel_id, days=365):
        from_date = datetime.datetime.today() - datetime.timedelta(days=days)
        pipeline = [
            {
                "$match": { "created_at": { "$gte": from_date}}
            },
            {
                "$group": {
                    "_id": "$channel_id",
                    "count": { "$sum": 1 }
                }
            },
            {
                "$sort": { "count": -1 }
            }
        ]
        total_channels = 0
        total_games = 0
        channel_rank = 0
        for idx, row in enumerate( cls.objects.aggregate(pipeline) ):
            if row['_id'] == channel_id:
                channel_rank = idx + 1
                channel_count = row['count']
            total_channels = idx
            total_games += row['count']
        if channel_rank == 0:
            channel_rank = total_channels
            channel_count = 0
        return (
            f"Total games recorded in the past {days} days: {total_games}\n"
            f"Rank of this channel:\n" +
            f"With {channel_count} games played this channel is No.{channel_rank} in total {total_channels + 1} channels.\n"
        )

class TgChannel(Document):
    tg_id = fields.IntField(primary=True)
    games_counter = fields.IntField(default=0)
    theme = fields.StringField(default = 'dark')
    current_game_type = fields.StringField(default = 'none')
    current_game_id = fields.ObjectIdField()
    announcement_timestamp = fields.DateTimeField(default=datetime.datetime.utcnow)

    meta = {
      'indexes': ['tg_id']
    }

    def __str__(self):
      return f'channel:{self.tg_id}, games:{self.games_counter}, current_game:{self.current_game_type}, current_game_id:{self.current_game_id}'

    def current_game(self):
      if self.current_game_type == 'WordSquadGame':
        return WordSquadGame.objects(pk=self.current_game_id).first()
      elif self.current_game_type == 'FofGame':
        return FofGame.objects(pk=self.current_game_id).first()

    def start_game(self, game):
      self.current_game_type = game.__class__.__name__
      self.current_game_id = game.pk
      self.save()

    @classmethod
    def find_or_create(cls, tg_channel_id):
      channel = cls.objects(tg_id=tg_channel_id).first()
      if channel is None:
        channel = TgChannel(
          tg_id = tg_channel_id
        )
        channel.save()
      return channel

    def in_trial_mode(self):
      return self.games_counter < 10

class FofGame(Document):
    channel_id = fields.IntField()
    secret_word = fields.StringField()
    synonyms = fields.ListField(fields.StringField(), default=[])
    antonyms = fields.ListField(fields.StringField(), default=[])
    revealed = fields.ListField(fields.StringField(), default=[])
    solved = fields.BooleanField(default=False)
    scores = fields.DictField(default = {})
    created_at = fields.DateTimeField(default=datetime.datetime.utcnow)
    guesses = fields.EmbeddedDocumentListField(WordGuess)
    rating = ''
    difficulty = 'Normal'
    disclosed_chars = 0

    meta = {
        'indexes': ['channel_id', 'solved']
    }

    def __str__(self):
        return f'{self.channel_id}:{self.secret_word}:{self.solved}'

    def add_score(self, user: TgUser, score: int) -> None:
        if user.name in self.scores.keys():
            self.scores[user.name] += score
        else:
            self.scores[user.name] = score

    def add_guess(self, guess: WordGuess) -> None:
        self.guesses.append(guess)
        if guess.guess == self.secret_word:
            self.solved = True
            self.add_score(guess.by_user, SCORES['game'])
        elif guess.guess in self.synonyms or guess.guess in self.antonyms:
            self.add_score(guess.by_user, SCORES['splash'])
        self.save()

    def bonus_points(self):
        return max(50 - 5 * len(self.guesses), 0)

    def print_score(self):
        return (
            'Game scores: \n' +
            top_players(self.scores)
        )

    def disclose_char(self, counter):
        self.disclosed_chars = int(log2(counter)) if counter > 0 else 0
        logger.info(f'counter: {counter}, disclosed_chars: {self.disclosed_chars}')

    def draw(self, theme, size=100):
        with SpooledTemporaryFile() as in_memory_file:
            word = str(self.secret_word)
            length = len(word)
            img = Image.new('RGB', (size * length, int(size * length * 0.4)), color = get_theme(theme)['bg'])
            font = ImageFont.truetype("nk57-monospace-no-rg.ttf", int(size * 0.9))
            draw = ImageDraw.Draw(img)
            # main letters
            for idx, char in enumerate(self.secret_word[:self.disclosed_chars] + '?' * (length - self.disclosed_chars)):
                draw.rectangle([int(size * (0.05 + idx)), int(size * 0.07), int(size * (idx + 0.9)) , int(size * 0.97)], outline='grey', width=3, fill=get_theme(theme)['fill_colors'][0 if char == '?' else 2])
                draw.text((int(size * (0.15 + idx)), 0), char.upper(), font=font, fill=get_theme(theme)['font_colors'][0 if char == '?' else 2])
            # available letters
            font = ImageFont.truetype("nk57-monospace-no-rg.ttf", int(size * 0.2))
            hints = ''
            line_count = 0
            for i in self.revealed:
                if line_count > 20:
                    hints += f'\n{i} '
                    line_count = len(i) + 1
                else:
                    hints += f'{i} '
                    line_count += len(i) + 1
            draw.text((int(size * 0.1), int(size * 1.1)), hints, font=font, fill=get_theme(theme)['font_colors'][3], spacing=4)

            img.save(in_memory_file, 'png')
            in_memory_file.seek(0)
            png_data = in_memory_file.read()
            return png_data

    @classmethod
    def start(cls, channel_id):
        game = FofGame()
        secret_word = Word.pick_fof()
        game.channel_id = channel_id
        game.secret_word = secret_word.word.lower()
        game.synonyms = secret_word.synonyms
        game.antonyms = secret_word.antonyms
        game.rating = secret_word.rating()
        game.difficulty = secret_word.difficulty()
        # give 3 synonyms as hints
        for i in range(3):
            if len(game.synonyms) == 0:
                break
            hint = random.choice(game.synonyms)
            game.revealed.append(hint)
            game.synonyms.remove(hint)
        # give 2 antonyms as hints
        for i in range(2):
            if len(game.antonyms) == 0:
                break
            hint = random.choice(game.antonyms)
            game.revealed.append(hint)
            game.antonyms.remove(hint)
        game.save()
        return game

    @classmethod
    @redis_cached
    def total_points(cls, channel_id, days=30):
        from_date = datetime.datetime.today() - datetime.timedelta(days)
        records = {}
        for game in cls.objects(channel_id=channel_id, solved=True, created_at__gte=from_date).all():
            for k, v in game.scores.items():
                if k in records.keys():
                    records[k] += v
                else:
                    records[k] = v
        return (
            f'FoF Leaderboard({days} days) of this channel:\n' +
            top_players(records)
        )
