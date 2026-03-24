from django.db import models


class Genre(models.TextChoices):
    POP = "POP", "Pop"
    ROCK = "ROCK", "Rock"
    JAZZ = "JAZZ", "Jazz"
    HIP_HOP = "HIP_HOP", "Hip Hop"
    CLASSICAL = "CLASSICAL", "Classical"
    COUNTRY = "COUNTRY", "Country"
    RNB = "RNB", "R&B"

class Singer(models.TextChoices):
    BOY = "BOY", "Boy"
    GIRL = "GIRL", "Girl"