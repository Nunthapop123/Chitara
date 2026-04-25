import requests
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
            "song_id": song.id,
            "task_id": song.task_id,
            "title": song.title,
            "status": "SUCCESS",
            "audio_url": song.audio_url
        }

    def check_status(self, task_id: str) -> Dict[str, Any]:
        return {
            "song_id": None,
            "task_id": task_id,
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
            "prompt": song.description[:5000],  
            "style": f"{song.song_genre}, {song.mood}"[:1000], 
            "title": str(song.title)[:80],
            "customMode": True,
            "instrumental": False,
            "callBackUrl": getattr(settings, "SUNO_CALLBACK_URL", "https://example.com/callback"),
            "model": "V4_5ALL",
        }

        callback_url = getattr(settings, "SUNO_CALLBACK_URL", "")
        if callback_url:
            payload["callBackUrl"] = callback_url

        # Optional advanced parameters from docs.
        optional_fields = {
            "personaId": getattr(settings, "SUNO_PERSONA_ID", None),
            "personaModel": getattr(settings, "SUNO_PERSONA_MODEL", None),
            "negativeTags": getattr(settings, "SUNO_NEGATIVE_TAGS", None),
            "vocalGender": getattr(settings, "SUNO_VOCAL_GENDER", None),
            "styleWeight": getattr(settings, "SUNO_STYLE_WEIGHT", None),
            "weirdnessConstraint": getattr(settings, "SUNO_WEIRDNESS_CONSTRAINT", None),
            "audioWeight": getattr(settings, "SUNO_AUDIO_WEIGHT", None),
        }
        for key, value in optional_fields.items():
            if value is not None and value != "":
                payload[key] = value
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            task_id = None
            if isinstance(data, list) and len(data) > 0:
                task_id = data[0].get("id")
            elif isinstance(data, dict):
                inner_data = data.get("data")
                if isinstance(inner_data, dict):
                    task_id = inner_data.get("taskId") or inner_data.get("id")
                elif isinstance(inner_data, list) and len(inner_data) > 0:
                    task_id = inner_data[0].get("id") or inner_data[0].get("taskId")
                    
                if not task_id:
                    task_id = data.get("id") or data.get("taskId")
                
            if task_id:
                song.task_id = task_id
                song.status = GeneratedSong.GenerationStatus.PENDING
                song.save()
                return {"status": "PENDING", "task_id": task_id, "response": data}
            else:
                song.status = GeneratedSong.GenerationStatus.FAILED
                song.save()
                return {"status": "FAILED", "error": "No task ID received.", "response": data}
                
        except requests.RequestException as e:
            song.status = GeneratedSong.GenerationStatus.FAILED
            song.save()
            return {"status": "FAILED", "error": str(e)}

    def check_status(self, task_id: str) -> Dict[str, Any]:
        """Poll the record-info endpoint to get status."""
        url = f"{self.BASE_URL}/generate/record-info"
        
        try:
            response = requests.get(url, headers=self.headers, params={"taskId": task_id}, timeout=30)
            # Backward compatibility for response variants that still expect ids.
            if response.status_code >= 400:
                response = requests.get(url, headers=self.headers, params={"ids": task_id}, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Handle envelope variants, e.g. {data: {...}} or {data: [...]} or plain list.
            if isinstance(data, list) and len(data) > 0:
                record = data[0]
            elif isinstance(data, dict) and "data" in data:
                record = data["data"][0] if isinstance(data["data"], list) and len(data["data"]) > 0 else data["data"]
            else:
                record = data

            status = record.get("status", "PENDING")
            audio_url = record.get("audio_url") or record.get("audioUrl")
            
            # Update the DB if we find the song
            try:
                song = GeneratedSong.objects.get(task_id=task_id)
                # Map API status to Choice
                if status == "SUCCESS":
                    song.status = GeneratedSong.GenerationStatus.SUCCESS
                    if audio_url:
                        song.audio_url = audio_url
                elif status == "TEXT_SUCCESS":
                    song.status = GeneratedSong.GenerationStatus.TEXT_SUCCESS
                elif status == "FIRST_SUCCESS":
                    song.status = GeneratedSong.GenerationStatus.FIRST_SUCCESS
                elif status == "FAILED":
                    song.status = GeneratedSong.GenerationStatus.FAILED
                elif status == "error":
                    song.status = GeneratedSong.GenerationStatus.FAILED
                else:
                    song.status = GeneratedSong.GenerationStatus.PENDING
                song.save()
            except GeneratedSong.DoesNotExist:
                pass
                
            return {
                "status": status,
                "audio_url": audio_url,
                "response": data
            }
            
        except requests.RequestException as e:
             return {"status": "FAILED", "error": str(e)}


def get_song_generator() -> SongGeneratorStrategy:
    """Factory function to get the active song generator strategy."""
    strategy_name = getattr(settings, 'GENERATOR_STRATEGY', 'mock').lower()
    
    if strategy_name == 'suno':
        return SunoSongGeneratorStrategy()
    
    return MockSongGeneratorStrategy()
