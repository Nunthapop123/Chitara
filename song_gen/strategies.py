import os
import requests
import time
from abc import ABC, abstractmethod
from django.conf import settings
from typing import Dict, Any

from .models.generated_song import GeneratedSong

class SongGeneratorStrategy(ABC):
    """Abstract base class for song generation strategies."""
    
    @abstractmethod
    def generate(self, song: GeneratedSong) -> Dict[str, Any]:
        """
        Initiate the song generation process.
        Returns a dictionary with status or result details.
        """
        pass
    
    @abstractmethod
    def check_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check the status of a generation task.
        """
        pass

class MockSongGeneratorStrategy(SongGeneratorStrategy):
    """Mock strategy that immediately returns success without external calls."""
    
    def generate(self, song: GeneratedSong) -> Dict[str, Any]:
        # Assign dummy values
        song.status = GeneratedSong.GenerationStatus.SUCCESS
        song.audio_url = "https://example.com/mock-audio.mp3"
        song.task_id = f"mock-task-{song.id}"
        song.save()
        
        return {
            "status": "SUCCESS",
            "task_id": song.task_id,
            "audio_url": song.audio_url
        }

    def check_status(self, task_id: str) -> Dict[str, Any]:
        return {
            "status": "SUCCESS",
            "audio_url": "https://example.com/mock-audio.mp3"
        }

class SunoSongGeneratorStrategy(SongGeneratorStrategy):
    """Strategy that integrates with api.sunoapi.org."""
    
    BASE_URL = "https://api.sunoapi.org/api/v1"
    
    def __init__(self):
        self.api_key = getattr(settings, 'SUNO_API_KEY', '')
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def generate(self, song: GeneratedSong) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("SUNO_API_KEY is not configured in settings.")
            
        url = f"{self.BASE_URL}/generate"
        payload = {
            "prompt": song.description,
            "tags": f"{song.song_genre}, {song.mood}",
            "title": song.title,
            "make_instrumental": False,
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            # The API usually returns an array of tasks or a task ID
            # Assuming standard Suno API behavior, we might get multiple items or a single task_id
            # We'll assume the response contains a taskId or we take the First element's id
            # Since the API often returns an array of objects `[{"id": "...", ...}]` or a dict
            # Let's handle both. Or if the user just says "includes the returned taskId".
            task_id = None
            if isinstance(data, list) and len(data) > 0:
                task_id = data[0].get("id")
            elif isinstance(data, dict):
                task_id = data.get("id") or data.get("taskId")
                
            if task_id:
                song.task_id = task_id
                song.status = GeneratedSong.GenerationStatus.PENDING
                song.save()
                return {"status": "PENDING", "task_id": task_id}
            else:
                song.status = GeneratedSong.GenerationStatus.FAILED
                song.save()
                return {"status": "FAILED", "error": "No task ID received."}
                
        except requests.RequestException as e:
            song.status = GeneratedSong.GenerationStatus.FAILED
            song.save()
            return {"status": "FAILED", "error": str(e)}

    def check_status(self, task_id: str) -> Dict[str, Any]:
        """Poll the record-info endpoint to get status."""
        url = f"{self.BASE_URL}/generate/record-info?taskId={task_id}"
        # Some API versions use ?ids= or similar, we'll use what the user provided:
        # GET https://api.sunoapi.org/api/v1/generate/record-info using Bearer token
        
        try:
            # Actually the url in prompt: GET https://api.sunoapi.org/api/v1/generate/record-info
            # Assuming we need to pass ids as query param, typically ?ids=task_id
            response = requests.get(f"{self.BASE_URL}/generate/record-info?ids={task_id}", headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            # Often returns a list of records
            if isinstance(data, list) and len(data) > 0:
                record = data[0]
            elif isinstance(data, dict) and "data" in data:
                record = data["data"][0] if isinstance(data["data"], list) and len(data["data"]) > 0 else data
            else:
                record = data

            status = record.get("status", "PENDING")
            audio_url = record.get("audio_url")
            
            # Update the DB if we find the song
            try:
                song = GeneratedSong.objects.get(task_id=task_id)
                # Map API status to Choice
                if status == "SUCCESS":
                    song.status = GeneratedSong.GenerationStatus.SUCCESS
                    if audio_url:
                        song.audio_url = audio_url
                elif status == "FAILED":
                    song.status = GeneratedSong.GenerationStatus.FAILED
                elif status == "error":
                    song.status = GeneratedSong.GenerationStatus.FAILED
                # Could handle TEXT_SUCCESS, FIRST_SUCCESS as well if API returns them
                song.save()
            except GeneratedSong.DoesNotExist:
                pass
                
            return {
                "status": status,
                "audio_url": audio_url
            }
            
        except requests.RequestException as e:
             return {"status": "FAILED", "error": str(e)}


def get_song_generator() -> SongGeneratorStrategy:
    """Factory function to get the active song generator strategy."""
    strategy_name = getattr(settings, 'GENERATOR_STRATEGY', 'mock').lower()
    
    if strategy_name == 'suno':
        return SunoSongGeneratorStrategy()
    
    return MockSongGeneratorStrategy()
