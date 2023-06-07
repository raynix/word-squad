from mongoengine import Document, fields
import random
import requests

def sanitize(string):
   if string is None:
      return ''
   return string.replace(".", "_")

class Word(Document):
   word = fields.StringField()
   definition = fields.ListField(default=[])
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

class TgChannel(Document):
   tg_id = fields.IntField(primary=True)
   games_counter = fields.IntField(default=0)

   meta = {
      'indexes': ['tg_id']
   }

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
