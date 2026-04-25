from django.apps import AppConfig


class SongGenConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'song_gen'

    def ready(self):
        import song_gen.signals
