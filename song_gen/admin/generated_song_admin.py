from django.contrib import admin
from song_gen.models import GeneratedSong


@admin.register(GeneratedSong)
class GeneratedSongAdmin(admin.ModelAdmin):
    list_display = ('title', 'song_genre', 'singer_choice', 'mood', 'duration', 'created_at', 'generated_by')
    list_filter = ('song_genre', 'singer_choice')
    search_fields = ('title', 'mood', 'description')
    readonly_fields = ('created_at',)
