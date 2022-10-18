from nltk.corpus import words
from random import random
from PIL import Image, ImageDraw, ImageFont
from tempfile import SpooledTemporaryFile

import re

CORRECT_LETTER = 2
MISPLACE_LETTER = 1
WRONG_LETTER = 0

colors = [
    (188,188,188),
    (220,220,60),
    (60,250,60)
]

class WordGuess:

    def __init__(self, secret, guess) -> None:
        self.guess = guess
        self.results = {}
        for idx, letter in enumerate(guess):
            if letter == secret[idx]:
                self.results[idx] = CORRECT_LETTER
            elif letter in secret:
                self.results[idx] = MISPLACE_LETTER
            else:
                self.results[idx] = WRONG_LETTER

    def draw(self):
        with SpooledTemporaryFile() as in_memory_file:
            img = Image.new('RGB', (100*len(self.guess), 100), color = (240,240,240))
            font = ImageFont.truetype("nk57-monospace-no-rg.ttf", 88)
            draw = ImageDraw.Draw(img)
            for idx, correctness in self.results.items():
                draw.text((10 + 92 * idx, 0), self.guess[idx].upper(), font=font, fill=colors[correctness])
            img.save(in_memory_file, 'png')
            in_memory_file.seek(0)
            png_data = in_memory_file.read()
            return png_data


class WordSquadGame:
    def __init__(self) -> None:
        self.words5 = [x for x in words.words('en') if re.match( '^[a-z]{5}$', x)]
        self.secret_word = self.words5[int((len(self.words5) - 1) * random())]
        self.guesses = []
