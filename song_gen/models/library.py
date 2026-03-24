from django.db import models
from .registered_user import RegisteredUser


class Library(models.Model):
    owner = models.OneToOneField(
        RegisteredUser,
        on_delete=models.CASCADE,
        related_name='library',
    )

    class Meta:
        verbose_name_plural = "Libraries"

    def __str__(self):
        return f"Library of {self.owner.email}"
