from django.db import models, connection
from mongoengine import Document, fields

from collections import namedtuple

def namedtuplefetchall(cursor):
    "Return all rows from a cursor as a namedtuple"
    desc = cursor.description
    nt_result = namedtuple('Result', [col[0] for col in desc])
    return [nt_result(*row) for row in cursor.fetchall()]

class Word(models.Model):
   class Meta:
      db_table = 'words'
   wordid = models.AutoField(primary_key=True)
   word = models.CharField()

   def difficulty(self):
      with connection.cursor() as cursor:
         cursor.execute("select count(sw2.word) as count FROM words AS sw LEFT JOIN senses AS s USING (wordid) LEFT JOIN synsets AS y USING (synsetid) LEFT JOIN senses AS s2 ON (y.synsetid = s2.synsetid) LEFT JOIN words AS sw2 ON (sw2.wordid = s2.wordid) WHERE sw.wordid <> sw2.wordid AND sw.word = '{self.word}'")
         synonyms_count = namedtuplefetchall(cursor)[0].count
         if synonyms_count == 0:
            return 'Ultra hard!'
         elif synonyms_count < 3:
            return 'Very hard'
         elif synonyms_count < 7:
            return 'Hard'
         elif synonyms_count < 15:
            return 'Normal'
         else:
            return 'Easy'

   @classmethod
   def is_english(cls, input):
      if cls.objects.filter(word=input).first():
         return True
      else:
         return False

   @classmethod
   def pick_one(cls, length):
      return cls.objects.raw(f"select * from words where word regexp '^[a-z]{{{length}}}$' order by rand() limit 1")[0]

   @classmethod
   def synonyms(cls, word):
      with connection.cursor() as cursor:
         cursor.execute(f"select sw2.word FROM words AS sw LEFT JOIN senses AS s USING (wordid) LEFT JOIN synsets AS y USING (synsetid) LEFT JOIN senses AS s2 ON (y.synsetid = s2.synsetid) LEFT JOIN words AS sw2 ON (sw2.wordid = s2.wordid) WHERE sw2.wordid <> sw.wordid AND sw.word = '{word}' LIMIT 3")
         return [ w.word for w in namedtuplefetchall(cursor) ]

class TgUser(Document):
   tg_user_id = fields.IntField(primary=True)
   name = fields.StringField()
   address = fields.StringField()

   @classmethod
   def find_or_create(cls, tg_user_id, first_name, last_name):
      user = TgUser.objects(tg_user_id=tg_user_id).first()
      if user is None:
         user = TgUser(
            tg_user_id = tg_user_id,
            name=f'{first_name or ""} {last_name or ""}',
         )
         user.save()
      return user
