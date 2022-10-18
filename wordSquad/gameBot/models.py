from django.db import models
from mongoengine import Document, fields

class TgUser(Document):
   name = fields.StringField()
   tg_id = fields.IntField()
   address = fields.StringField()
