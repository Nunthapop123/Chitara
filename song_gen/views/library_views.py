import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from song_gen.models import GeneratedSong
from song_gen.strategies import get_song_generator

from .auth_views import get_or_create_user

logger = logging.getLogger(__name__)


def library_view(request):
    user = get_or_create_user(request)
    if not user:
        return redirect('login')

    songs_needing_sync = GeneratedSong.objects.filter(
        library__owner=user,
        task_id__isnull=False,
        audio_url='',
    ).exclude(task_id='')[:10]

    if songs_needing_sync:
        generator = get_song_generator()
        for song in songs_needing_sync:
            try:
                generator.check_status(song.task_id)
            except Exception as e:
                logger.warning('Library sync failed for song %s: %s', song.id, e)

    songs = GeneratedSong.objects.filter(library__owner=user)
    return render(request, 'song_gen/library.html', {'songs': songs})


def shared_song_view(request, id):
    song = get_object_or_404(GeneratedSong, id=id)
    return render(request, 'song_gen/shared_song.html', {'song': song})


def delete_song_view(request, id):
    user = get_or_create_user(request)
    if not user:
        return redirect('login')

    if request.method == 'POST':
        song = get_object_or_404(GeneratedSong, id=id, library__owner=user)
        song.delete()

    return redirect('library')


def library_search_api(request):
    user = get_or_create_user(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    query = request.GET.get('q', '').strip()
    songs = GeneratedSong.objects.filter(library__owner=user)
    if query:
        songs = songs.filter(title__icontains=query)

    song_ids = list(songs.values_list('id', flat=True))
    return JsonResponse({'song_ids': song_ids})
