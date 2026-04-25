from django.contrib import admin
from song_gen.models import Library, GeneratedSong


class GeneratedSongInline(admin.TabularInline):
    model = GeneratedSong
    extra = 0
    readonly_fields = ('title', 'song_genre', 'status', 'created_at')
    can_delete = False


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ('owner',)
    search_fields = ('owner__email',)
    inlines = [GeneratedSongInline]
