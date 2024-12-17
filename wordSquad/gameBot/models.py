from mongoengine import Document, fields
import random
import requests
import re

def sanitize(string):
  if string is None:
    return ''
  return re.sub('[\\.\\$]', '_', string)

class Word(Document):
  word = fields.StringField()
  definition = fields.ListField(default=[])
  upvotes = fields.IntField(default = 0)
  downvotes = fields.IntField(default = 0)
  meta = {
    'indexes': ['word']
  }

  trials = [
    "Apple", "Basic", "Cloud", "Dolly", "Error",
    "Flour", "Great", "Hello", "Ideal", "Jewel",
    "Karma", "Label", "Mouse", "Naive", "Ocean",
    "Paper", "Quest", "Round", "Sleep", "Table",
    "Ultra", "Value", "World", "Yeast", "Zebra"
  ]

  def __str__(self):
    return self.word

  def difficulty(self):
    c = len(self.definition)
    if c == 1:
        return 'Ultra Hard'
    elif c == 2:
        return 'Very Hard'
    elif c == 3:
        return 'Hard'
    elif c <= 5:
        return 'Normal'
    else:
        return 'Easy'

  def synonyms(self):
    return ['Not implemented']

  def full_meanings(self):
    return [f"- {d['meaning']}" for d in self.definition ]

  def meanings(self):
    return [f"- {d['meaning']}" for d in self.definition[:3] ]

  def upvote(self):
    self.upvotes += 1
    self.save()

  def downvote(self):
    self.downvotes += 1
    self.save()

  def rating(self):
    if self.upvotes == 0 and self.downvotes == 0:
      hearts = 2
    else:
      hearts = 5 if self.downvotes == 0 else min(int(self.upvotes / self.downvotes * 2.5), 5)
    return '❤️' * hearts + '🤍' * (5 - hearts)

  @classmethod
  def find(cls, word):
    results = cls.objects(word__iexact=word)
    if len(results) > 0:
        return results[0]
    else:
        return None

  @classmethod
  def is_english(cls, input):
    return cls.objects(word__iexact=input).count()

  @classmethod
  def pick_trial(cls):
    return cls.objects.get(word=random.choice(cls.trials))

  @classmethod
  def pick_one(cls, length):
    picked = None
    pipeline = [
      {
        "$match": {"word": {"$regex": f"^[a-z]{{{length}}}$", "$options": 'i' }}
      },
      {
        "$sample": {"size": 1}
      }
    ]
    for row in cls.objects.aggregate(pipeline):
      #print(row)
      picked = cls.objects.get(id=row["_id"])
      break
    return picked

  @classmethod
  def ingest(cls, word) -> bool:
    resp = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower()}")
    if not resp.ok:
      return False
    json = resp.json()
    definitions = [
      { 'pos': meaning['partOfSpeech'], 'meaning': definition['definition'] } for meaning in json[0]['meanings'] for definition in meaning['definitions']
    ]
    new_word = Word(
      word = word,
      definition = definitions
    )
    new_word.save()
    return True

class TgUser(Document):
  tg_user_id = fields.IntField(primary=True)
  name = fields.StringField()
  address = fields.StringField()
  meta = {
    'indexes': ['tg_user_id']
  }

  @classmethod
  def find_or_create(cls, tg_user_id, first_name, last_name):
    user = TgUser.objects(tg_user_id=tg_user_id).first()
    if user is None:
        user = TgUser(
          tg_user_id = tg_user_id,
          name=f'{sanitize(first_name)} {sanitize(last_name)}',
        )
        user.save()
    return user
