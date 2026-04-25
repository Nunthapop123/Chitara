from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.conf import settings
from song_gen.models import GeneratedSong, Library, RegisteredUser
from song_gen.strategies import get_song_generator
import os
import uuid
import logging

logger = logging.getLogger(__name__)


GENRE_MAP = {
    "Pop": "POP",
    "Rock": "ROCK",
    "Jazz": "JAZZ",
    "Hip-Hop": "HIP_HOP",
    "Classical": "CLASSICAL",
    "Country": "COUNTRY",
    "R&B": "RNB",
}

SINGER_MAP = {
    "Boy": "BOY",
    "Girl": "GIRL",
}


def build_share_url(request, song_id):
    path = reverse('shared_song', args=[song_id])
    base_url = getattr(settings, 'SITE_BASE_URL', '').strip().rstrip('/')
    if base_url:
        return f"{base_url}{path}"
    return request.build_absolute_uri(path)


def store_cover_image(request, cover_file):
    if not cover_file:
        return ''

    file_extension = os.path.splitext(cover_file.name)[1] or '.png'
    safe_filename = f"covers/{uuid.uuid4().hex}{file_extension}"
    storage = FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)
    stored_name = storage.save(safe_filename, cover_file)
    return request.build_absolute_uri(storage.url(stored_name))

def landing_view(request):
    return render(request, 'song_gen/landing.html')

def login_view(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Django's default authenticate uses username, so we look up the user by email first
        user_obj = User.objects.filter(email=email).first()
        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
        else:
            user = None
            
        if user is not None:
            auth_login(request, user)
            return redirect('library')
        else:
            messages.error(request, "Invalid email or password.")
            
    return render(request, 'song_gen/login.html')

def register_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if not email or not password or not username:
            messages.error(request, "All fields are required.")
        elif User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
            messages.error(request, "Username or Email already registered.")
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            auth_login(request, user)
            
            # Sync to custom RegisteredUser schema
            reg_user, _ = RegisteredUser.objects.get_or_create(email=email)
            Library.objects.get_or_create(owner=reg_user)
            
            return redirect('library')
            
    return render(request, 'song_gen/register.html')

def logout_view(request):
    auth_logout(request)
    return redirect('landing')

def get_or_create_user(request):
    """Utility to get or create a RegisteredUser based on standard Django auth"""
    if request.user.is_authenticated:
        user, _ = RegisteredUser.objects.get_or_create(email=request.user.email)
        # Ensure library exists
        Library.objects.get_or_create(owner=user)
        return user
    return None

def library_view(request):
    user = get_or_create_user(request)
    if not user:
        return redirect('login')

    # Best-effort resync for songs that should be playable but are missing audio URL.
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
                logger.warning(f"Library sync failed for song {song.id}: {e}")

    songs = GeneratedSong.objects.filter(library__owner=user)
    return render(request, 'song_gen/library.html', {"songs": songs})

def generate_view(request):
    user = get_or_create_user(request)
    if not user:
        messages.error(request, "You must be logged in to access this page.")
        return redirect('login')
    
    if request.method == "POST":
        if user.daily_generation_count >= 20:
            messages.error(request, "Daily generation limit reached! You have no credits left.")
            return redirect('generate')

        raw_genre = request.POST.get('genre', '').strip()
        raw_singer = request.POST.get('singer', '').strip()
        mood = request.POST.get('mood', '').strip()
        description = request.POST.get('description', '').strip()
        title = request.POST.get('title', 'Untitled Track').strip() or 'Untitled Track'

        # Accept either enum values or legacy display labels.
        song_genre = raw_genre if raw_genre in dict(GeneratedSong._meta.get_field('song_genre').choices) else GENRE_MAP.get(raw_genre)
        singer_choice = raw_singer if raw_singer in dict(GeneratedSong._meta.get_field('singer_choice').choices) else SINGER_MAP.get(raw_singer)

        if not song_genre or not singer_choice or not mood:
            messages.error(request, "Invalid generation parameters. Please reselect genre, singer, and mood.")
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
            status=GeneratedSong.GenerationStatus.PENDING
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
            logger.error(f"Generation error: {e}")
            messages.error(request, f"Failed to start generation: {e}")
            song.delete()
            user.daily_generation_count -= 1
            user.save()
            return redirect('generate')

    return render(request, 'song_gen/generate.html')

def shared_song_view(request, id):
    song = get_object_or_404(GeneratedSong, id=id)
    return render(request, 'song_gen/shared_song.html', {"song": song})

def delete_song_view(request, id):
    user = get_or_create_user(request)
    if not user:
        return redirect('login')
        
    if request.method == "POST":
        song = get_object_or_404(GeneratedSong, id=id, library__owner=user)
        song.delete()
        messages.success(request, "Song deleted successfully.")
    return redirect('library')

def generation_status_view(request, id):
    user = get_or_create_user(request)
    if not user:
        return redirect('login')
        
    song = get_object_or_404(GeneratedSong, id=id, library__owner=user)
    return render(request, 'song_gen/generation_status.html', {"song": song})

def song_status_api(request, id):
    user = get_or_create_user(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
        
    song = get_object_or_404(GeneratedSong, id=id, library__owner=user)

    # Keep local DB in sync with provider status while frontend is polling.
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
            logger.warning(f"Status sync failed for song {song.id}: {e}")

    song.refresh_from_db()
    return JsonResponse({
        'status': song.status,
        'audio_url': song.audio_url,
        'title': song.title
    })


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
