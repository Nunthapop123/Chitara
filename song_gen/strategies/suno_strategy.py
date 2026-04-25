import os
from typing import Any, Dict

import requests
from django.conf import settings

from ..models.generated_song import GeneratedSong
from .strategy_base import SongGeneratorStrategy


class SunoSongGeneratorStrategy(SongGeneratorStrategy):
    """Strategy that integrates with api.sunoapi.org."""

    BASE_URL = 'https://api.sunoapi.org/api/v1'
    ALLOWED_MODELS = {'V3_5', 'V4', 'V4_5ALL', 'V4_5', 'V4_5PLUS', 'V6_5'}

    def __init__(self):
        self.api_key = getattr(settings, 'SUNO_API_KEY', '')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def _read_bool_config(self, name: str, default: bool = False) -> bool:
        value = getattr(settings, name, None)
        if value is None:
            value = os.getenv(name)
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    def _resolve_model(self) -> str:
        configured_model = getattr(settings, 'SUNO_MODEL', None)
        if configured_model is None:
            configured_model = os.getenv('SUNO_MODEL', 'V4')

        normalized_model = str(configured_model or '').strip().upper()
        if normalized_model in self.ALLOWED_MODELS:
            return normalized_model
        return 'V4'

    def _extract_task_id(self, payload: Any) -> str | None:
        if isinstance(payload, dict):
            for key in ('task_id', 'taskId', 'id'):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            for container_key in ('data', 'result'):
                nested = payload.get(container_key)
                nested_task_id = self._extract_task_id(nested)
                if nested_task_id:
                    return nested_task_id

        if isinstance(payload, list):
            for item in payload:
                nested_task_id = self._extract_task_id(item)
                if nested_task_id:
                    return nested_task_id

        return None

    def _extract_error_message(self, payload: Any) -> str:
        if isinstance(payload, dict):
            for key in ('message', 'msg', 'error', 'detail'):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            nested = payload.get('data')
            nested_message = self._extract_error_message(nested)
            if nested_message:
                return nested_message

        if isinstance(payload, list):
            for item in payload:
                nested_message = self._extract_error_message(item)
                if nested_message:
                    return nested_message

        return ''

    def _looks_like_audio_url(self, value: str) -> bool:
        lowered = value.lower()
        return (
            lowered.startswith('http://')
            or lowered.startswith('https://')
        ) and (
            '.mp3' in lowered
            or '.wav' in lowered
            or '.m4a' in lowered
            or 'audio' in lowered
        )

    def _extract_audio_url(self, payload: Any) -> str | None:
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
                nested_audio_url = self._extract_audio_url(value)
                if nested_audio_url:
                    return nested_audio_url

        if isinstance(payload, list):
            for item in payload:
                nested_audio_url = self._extract_audio_url(item)
                if nested_audio_url:
                    return nested_audio_url

        if isinstance(payload, str) and self._looks_like_audio_url(payload):
            return payload

        return None

    def generate(self, song: GeneratedSong) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError('SUNO_API_KEY is not configured in settings.')

        url = f'{self.BASE_URL}/generate'

        prompt_text = (song.description or '').strip()
        if not prompt_text:
            prompt_text = f'A {song.mood.lower()} {song.song_genre.lower()} song titled {song.title}.'

        payload = {
            'prompt': prompt_text[:5000],
            'style': f'{song.song_genre}, {song.mood}'[:1000],
            'title': str(song.title)[:80],
            'customMode': self._read_bool_config('SUNO_CUSTOM_MODE', False),
            'instrumental': self._read_bool_config('SUNO_INSTRUMENTAL', False),
            'callBackUrl': getattr(settings, 'SUNO_CALLBACK_URL', 'https://example.com/callback'),
            'model': self._resolve_model(),
        }

        callback_url = getattr(settings, 'SUNO_CALLBACK_URL', '')
        if callback_url:
            payload['callBackUrl'] = callback_url

        optional_fields = {
            'personaId': getattr(settings, 'SUNO_PERSONA_ID', None),
            'personaModel': getattr(settings, 'SUNO_PERSONA_MODEL', None),
            'negativeTags': getattr(settings, 'SUNO_NEGATIVE_TAGS', None),
            'vocalGender': getattr(settings, 'SUNO_VOCAL_GENDER', None),
            'styleWeight': getattr(settings, 'SUNO_STYLE_WEIGHT', None),
            'weirdnessConstraint': getattr(settings, 'SUNO_WEIRDNESS_CONSTRAINT', None),
            'audioWeight': getattr(settings, 'SUNO_AUDIO_WEIGHT', None),
        }
        for key, value in optional_fields.items():
            if value is not None and value != '':
                payload[key] = value

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=60)
            try:
                data = response.json()
            except ValueError:
                data = {'raw_response': response.text}

            if response.status_code >= 400:
                message = self._extract_error_message(data) or f'HTTP {response.status_code}'
                if 'model' in message.lower() and payload.get('model'):
                    message = f"{message} (model sent: {payload['model']})"
                song.status = GeneratedSong.GenerationStatus.FAILED
                song.save()
                return {'status': 'FAILED', 'error': message, 'response': data}

            task_id = self._extract_task_id(data)

            if task_id:
                song.task_id = task_id
                song.status = GeneratedSong.GenerationStatus.PENDING
                song.save()
                return {'status': 'PENDING', 'task_id': task_id, 'response': data}

            song.status = GeneratedSong.GenerationStatus.FAILED
            song.save()
            message = self._extract_error_message(data) or 'No task ID received from generation API.'
            return {'status': 'FAILED', 'error': message, 'response': data}

        except requests.RequestException as e:
            song.status = GeneratedSong.GenerationStatus.FAILED
            song.save()
            return {'status': 'FAILED', 'error': str(e)}

    def check_status(self, task_id: str) -> Dict[str, Any]:
        url = f'{self.BASE_URL}/generate/record-info'

        try:
            response = requests.get(url, headers=self.headers, params={'taskId': task_id}, timeout=30)
            if response.status_code >= 400:
                response = requests.get(url, headers=self.headers, params={'ids': task_id}, timeout=30)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                record = data[0]
            elif isinstance(data, dict) and 'data' in data:
                record = data['data'][0] if isinstance(data['data'], list) and len(data['data']) > 0 else data['data']
            else:
                record = data

            raw_status = str(record.get('status', 'PENDING') or 'PENDING')
            status = raw_status.upper()
            audio_url = self._extract_audio_url(record) or self._extract_audio_url(data)

            try:
                song = GeneratedSong.objects.get(task_id=task_id)
                if status == 'SUCCESS':
                    song.status = GeneratedSong.GenerationStatus.SUCCESS
                    if audio_url:
                        song.audio_url = audio_url
                elif status == 'TEXT_SUCCESS':
                    song.status = GeneratedSong.GenerationStatus.TEXT_SUCCESS
                elif status == 'FIRST_SUCCESS':
                    song.status = GeneratedSong.GenerationStatus.FIRST_SUCCESS
                elif status in {'FAILED', 'ERROR'}:
                    song.status = GeneratedSong.GenerationStatus.FAILED
                else:
                    song.status = GeneratedSong.GenerationStatus.PENDING
                song.save()
            except GeneratedSong.DoesNotExist:
                pass

            return {
                'status': status,
                'audio_url': audio_url,
                'response': data,
            }

        except requests.RequestException as e:
            return {'status': 'FAILED', 'error': str(e)}
