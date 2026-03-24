from django.db import models


class RegisteredUser(models.Model):
    email = models.EmailField(unique=True)
    daily_generation_count = models.IntegerField(default=0)

    def __str__(self):
        return self.email
