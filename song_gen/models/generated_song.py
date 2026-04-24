from django.db import models
from .enums import Genre, Singer
from .library import Library
from .registered_user import RegisteredUser


class GeneratedSong(models.Model):
    class GenerationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        TEXT_SUCCESS = 'TEXT_SUCCESS', 'Text Success'
        FIRST_SUCCESS = 'FIRST_SUCCESS', 'First Success'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'

    title = models.CharField(max_length=255)
    song_genre = models.CharField(
        max_length=20,
        choices=Genre.choices,
    )
    singer_choice = models.CharField(
        max_length=10,
        choices=Singer.choices,
    )
    mood = models.CharField(max_length=255)
    description = models.TextField()
    cover_image_url = models.CharField(
        max_length=2048,
        blank=True,
    )
    duration = models.IntegerField()
    share_url = models.CharField(
        max_length=2048,
        blank=True,
    )
    audio_url = models.CharField(
        max_length=2048,
        blank=True,
    )
    task_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        choices=GenerationStatus.choices,
        default=GenerationStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    library = models.ForeignKey(
        Library,
        on_delete=models.CASCADE,
        related_name='songs',
    )
    generated_by = models.ForeignKey(
        RegisteredUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_songs',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.song_genre}) — {self.created_at.date()}"
