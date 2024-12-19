from enum import Enum
from datetime import datetime
import sys
from mongoengine import Document, fields
import random
import requests
import re
import logging

from wordhoard import Antonyms, Synonyms

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

def sanitize(string):
  if string is None:
    return ''
  return re.sub('[\\.\\$]', '_', string)

class FofState(Enum):
  unknown = 'unknown'
  ready = 'ready'
  failed = 'failed'

class Word(Document):
  word = fields.StringField()
  definition = fields.ListField(default=[])
  upvotes = fields.IntField(default = 0)
  downvotes = fields.IntField(default = 0)
  antonyms = fields.ListField(default=[])
  synonyms = fields.ListField(default=[])
  fof = fields.EnumField(FofState, default=FofState.unknown)

  meta = {
    'indexes': ['word', 'fof']
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

  def prepare_synonyms(self):
    try:
      self.synonyms = [
        x.lower() for x in set(Synonyms(search_string=self.word).find_synonyms())
        if x.lower().find(self.word.lower()) == -1
      ]
    except Exception as e:
      logger.error(f"Error finding synonyms for {self.word}: {e}")

  def prepare_antonyms(self):
    try:
      self.antonyms = [
        x.lower() for x in set(Antonyms(search_string=self.word).find_antonyms())
        if x.lower().find(self.word.lower()) == -1
      ]
    except Exception as e:
      logger.error(f"Error finding antonyms for {self.word}: {e}")

  def prepare_thesaurus(self):
    self.prepare_synonyms()
    logger.info(f"Synonyms for {self.word}: {self.synonyms}")
    self.prepare_antonyms()
    logger.info(f"Antonyms for {self.word}: {self.antonyms}")
    self.fof = FofState.ready if len(self.synonyms) > 0 and len(self.antonyms) > 0 else FofState.failed
    self.save()

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
        "$match": {"word": {"$regex": f"^[a-zA-Z]{{{length}}}$" }}
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

class Announcement(Document):
  message = fields.StringField()
  created = fields.DateTimeField(default = datetime.now())
  meta = {
    'indexes': ['created']
  }

  def __str__(self):
    return f'{self.created}: {self.message}'

  @classmethod
  def fetch_new_messages(cls, channel_timestamp: datetime):
    return [a.message for a in Announcement.objects(created__gt=channel_timestamp)]
