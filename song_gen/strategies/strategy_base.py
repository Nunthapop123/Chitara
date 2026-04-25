from abc import ABC, abstractmethod
from typing import Any, Dict

from ..models.generated_song import GeneratedSong


class SongGeneratorStrategy(ABC):
    """Abstract base class for song generation strategies."""

    @abstractmethod
    def generate(self, song: GeneratedSong) -> Dict[str, Any]:
        """Initiate the song generation process."""
        raise NotImplementedError

    @abstractmethod
    def check_status(self, task_id: str) -> Dict[str, Any]:
        """Check the status of a generation task."""
        raise NotImplementedError
