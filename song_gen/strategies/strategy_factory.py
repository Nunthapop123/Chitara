from django.conf import settings

from .mock_strategy import MockSongGeneratorStrategy
from .strategy_base import SongGeneratorStrategy
from .suno_strategy import SunoSongGeneratorStrategy


def get_song_generator() -> SongGeneratorStrategy:
    """Factory function to get the active song generator strategy."""
    strategy_name = getattr(settings, 'GENERATOR_STRATEGY', 'mock').lower()

    if strategy_name == 'suno':
        return SunoSongGeneratorStrategy()

    return MockSongGeneratorStrategy()
