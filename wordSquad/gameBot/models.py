from mongoengine import Document, fields

class Word(Document):
   word = fields.StringField()
   definition = fields.ListField(default=[])
   meta = {
      'indexes': ['word']
   }

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

   def meanings(self):
      return [f"- {d['meaning']}" for d in self.definition ]

   @classmethod
   def is_english(cls, input):
      return cls.objects(word__iexact=input).count()

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
            name=f'{first_name or ""} {last_name or ""}',
         )
         user.save()
      return user
