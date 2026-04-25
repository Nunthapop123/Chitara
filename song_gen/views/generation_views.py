import logging
import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from song_gen.models import GeneratedSong, Library
from song_gen.strategies import get_song_generator

from .auth_views import get_or_create_user

logger = logging.getLogger(__name__)


GENRE_MAP = {
    'Pop': 'POP',
    'Rock': 'ROCK',
    'Jazz': 'JAZZ',
    'Hip-Hop': 'HIP_HOP',
    'Classical': 'CLASSICAL',
    'Country': 'COUNTRY',
    'R&B': 'RNB',
}

SINGER_MAP = {
    'Boy': 'BOY',
    'Girl': 'GIRL',
}


def build_share_url(request, song_id):
    path = reverse('shared_song', args=[song_id])
    base_url = getattr(settings, 'SITE_BASE_URL', '').strip().rstrip('/')
    if base_url:
        return f'{base_url}{path}'
    return request.build_absolute_uri(path)


def store_cover_image(request, cover_file):
    if not cover_file:
        return ''

    file_extension = os.path.splitext(cover_file.name)[1] or '.png'
    safe_filename = f'covers/{uuid.uuid4().hex}{file_extension}'
    storage = FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)
    stored_name = storage.save(safe_filename, cover_file)
    return request.build_absolute_uri(storage.url(stored_name))


def generate_view(request):
    user = get_or_create_user(request)
    if not user:
        return redirect('login')

    if request.method == 'POST':
        if user.daily_generation_count >= 20:
            return redirect('generate')

        raw_genre = request.POST.get('genre', '').strip()
        raw_singer = request.POST.get('singer', '').strip()
        mood = request.POST.get('mood', '').strip()
        description = request.POST.get('description', '').strip()
        title = request.POST.get('title', 'Untitled Track').strip() or 'Untitled Track'

        song_genre = raw_genre if raw_genre in dict(GeneratedSong._meta.get_field('song_genre').choices) else GENRE_MAP.get(raw_genre)
        singer_choice = raw_singer if raw_singer in dict(GeneratedSong._meta.get_field('singer_choice').choices) else SINGER_MAP.get(raw_singer)

        if not song_genre or not singer_choice or not mood:
            return redirect('generate')

        library, _ = Library.objects.get_or_create(owner=user)

        song = GeneratedSong.objects.create(
            title=title,
            song_genre=song_genre,
            singer_choice=singer_choice,
            mood=mood,
            description=description,
            duration=120,
            library=library,
            generated_by=user,
            status=GeneratedSong.GenerationStatus.PENDING,
        )

        cover_file = request.FILES.get('cover')
        cover_image_url = store_cover_image(request, cover_file)
        share_url = build_share_url(request, song.id)

        if cover_image_url or share_url:
            if cover_image_url:
                song.cover_image_url = cover_image_url
            song.share_url = share_url
            song.save(update_fields=['cover_image_url', 'share_url'])

        user.daily_generation_count += 1
        user.save()

        generator = get_song_generator()
        try:
            result = generator.generate(song)
            if isinstance(result, dict) and result.get('status') == 'FAILED':
                raise Exception(result.get('error', 'Suno API error or no credits.'))

            return redirect('generation_status', id=song.id)
        except Exception as e:
            logger.error('Generation error: %s', e)
            song.delete()
            user.daily_generation_count -= 1
            user.save()
            return redirect('generate')

    return render(request, 'song_gen/generate.html')


def generation_status_view(request, id):
    user = get_or_create_user(request)
    if not user:
        return redirect('login')

    song = get_object_or_404(GeneratedSong, id=id, library__owner=user)
    return render(request, 'song_gen/generation_status.html', {'song': song})


def song_status_api(request, id):
    user = get_or_create_user(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    song = get_object_or_404(GeneratedSong, id=id, library__owner=user)

    should_sync = (
        song.task_id and (
            song.status in {
                GeneratedSong.GenerationStatus.PENDING,
                GeneratedSong.GenerationStatus.TEXT_SUCCESS,
                GeneratedSong.GenerationStatus.FIRST_SUCCESS,
            }
            or (song.status == GeneratedSong.GenerationStatus.SUCCESS and not song.audio_url)
        )
    )

    if should_sync:
        try:
            generator = get_song_generator()
            result = generator.check_status(song.task_id)
            latest_status = (result or {}).get('status')
            if isinstance(latest_status, str):
                normalized_status = latest_status.upper()
                if normalized_status in {
                    GeneratedSong.GenerationStatus.PENDING,
                    GeneratedSong.GenerationStatus.TEXT_SUCCESS,
                    GeneratedSong.GenerationStatus.FIRST_SUCCESS,
                    GeneratedSong.GenerationStatus.SUCCESS,
                    GeneratedSong.GenerationStatus.FAILED,
                }:
                    song.refresh_from_db()
        except Exception as e:
            logger.warning('Status sync failed for song %s: %s', song.id, e)

    song.refresh_from_db()
    return JsonResponse({
        'status': song.status,
        'audio_url': song.audio_url,
        'title': song.title,
    })
