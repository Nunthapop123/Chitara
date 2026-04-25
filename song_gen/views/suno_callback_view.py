import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from song_gen.models import GeneratedSong


def _looks_like_audio_url(value: str) -> bool:
    lowered = value.lower()
    return (
        lowered.startswith('http://') or lowered.startswith('https://')
    ) and (
        '.mp3' in lowered or '.wav' in lowered or '.m4a' in lowered or 'audio' in lowered
    )


def _extract_audio_url(payload):
    if isinstance(payload, dict):
        for key in (
            'audio_url',
            'audioUrl',
            'source_audio_url',
            'sourceAudioUrl',
            'stream_url',
            'streamUrl',
            'media_url',
            'mediaUrl',
        ):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        for value in payload.values():
            nested_audio_url = _extract_audio_url(value)
            if nested_audio_url:
                return nested_audio_url

    if isinstance(payload, list):
        for item in payload:
            nested_audio_url = _extract_audio_url(item)
            if nested_audio_url:
                return nested_audio_url

    if isinstance(payload, str) and _looks_like_audio_url(payload):
        return payload

    return None

@csrf_exempt
def suno_callback(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            outer_data = body.get('data', body)

            callback_type = (
                outer_data.get('callbackType')
                or outer_data.get('type')
                or body.get('callbackType')
                or body.get('type')
                or ''
            )
            callback_type = str(callback_type).strip().lower()

            task_id = (
                outer_data.get('task_id')
                or outer_data.get('taskId')
                or body.get('task_id')
                or body.get('taskId')
            )
            task_id = str(task_id).strip() if task_id else ''

            items = outer_data.get('data') or body.get('data') or []
            if isinstance(items, dict):
                items = [items]

            if not task_id:
                return JsonResponse({'status': 'ignored', 'message': 'No task_id found'}, status=200)

            try:
                song = GeneratedSong.objects.get(task_id=task_id)
            except GeneratedSong.DoesNotExist:
                return JsonResponse({'status': 'ignored', 'message': 'Task ID not found in database'}, status=200)

            if callback_type in ['complete', 'first', 'success']:
                audio_url = _extract_audio_url(outer_data) or _extract_audio_url(body) or _extract_audio_url(items)
                
                if audio_url:
                    song.audio_url = audio_url
                    
                song.status = GeneratedSong.GenerationStatus.SUCCESS
                song.save()
            elif callback_type in ['error', 'failed', 'fail']:
                song.status = GeneratedSong.GenerationStatus.FAILED
                song.save()
            elif callback_type == 'text':
                song.status = GeneratedSong.GenerationStatus.TEXT_SUCCESS
                song.save()

            return JsonResponse({'status': 'success'}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
