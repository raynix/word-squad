from django.db import models
from mongoengine import Document, fields

class Word(models.Model):
   class Meta:
      db_table = 'words'
   wordid = models.AutoField(primary_key=True)
   word = models.CharField()

   @classmethod
   def is_english(cls, input):
      if cls.objects.filter(word=input).first():
         return True
      else:
         return False

class TgUser(Document):
   name = fields.StringField()
   tg_id = fields.IntField()
   address = fields.StringField()
