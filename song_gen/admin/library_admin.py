from django.contrib import admin
from song_gen.models import Library


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ('owner',)
    search_fields = ('owner__email',)
