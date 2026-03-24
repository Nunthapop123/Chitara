from django.contrib import admin
from song_gen.models import RegisteredUser


@admin.register(RegisteredUser)
class RegisteredUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'daily_generation_count')
    search_fields = ('email',)
