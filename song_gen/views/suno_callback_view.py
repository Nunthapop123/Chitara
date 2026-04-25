import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from song_gen.models import GeneratedSong

@csrf_exempt
def suno_callback(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            outer_data = body.get('data', {})
            callback_type = outer_data.get('callbackType')
            task_id = outer_data.get('task_id')
            items = outer_data.get('data', [])

            if not task_id:
                return JsonResponse({'status': 'ignored', 'message': 'No task_id found'}, status=200)

            try:
                song = GeneratedSong.objects.get(task_id=task_id)
            except GeneratedSong.DoesNotExist:
                return JsonResponse({'status': 'ignored', 'message': 'Task ID not found in database'}, status=200)

            if callback_type in ['complete', 'first']:
                audio_url = None
                if items and isinstance(items, list):
                    audio_url = items[0].get('audio_url')
                
                if audio_url:
                    song.audio_url = audio_url
                    
                song.status = GeneratedSong.GenerationStatus.SUCCESS
                song.save()
            elif callback_type == 'error':
                song.status = GeneratedSong.GenerationStatus.FAILED
                song.save()
            elif callback_type == 'text':
                song.status = GeneratedSong.GenerationStatus.TEXT_SUCCESS
                song.save()

            return JsonResponse({'status': 'success'}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
