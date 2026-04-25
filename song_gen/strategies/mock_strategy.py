from typing import Any, Dict

from ..models.generated_song import GeneratedSong
from .strategy_base import SongGeneratorStrategy


class MockSongGeneratorStrategy(SongGeneratorStrategy):
    """Mock strategy that immediately returns success without external calls."""

    def generate(self, song: GeneratedSong) -> Dict[str, Any]:
        song.status = GeneratedSong.GenerationStatus.SUCCESS
        song.audio_url = 'https://example.com/mock-audio.mp3'
        song.task_id = f'mock-task-{song.id}'
        song.save()

        return {
            'song_id': song.id,
            'task_id': song.task_id,
            'title': song.title,
            'status': 'SUCCESS',
            'audio_url': song.audio_url,
        }

    def check_status(self, task_id: str) -> Dict[str, Any]:
        return {
            'song_id': None,
            'task_id': task_id,
            'status': 'SUCCESS',
            'audio_url': 'https://example.com/mock-audio.mp3',
        }
