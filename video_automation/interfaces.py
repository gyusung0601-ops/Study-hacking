from abc import ABC, abstractmethod
from typing import List

class ScriptGenerator(ABC):
    @abstractmethod
    def generate_script(self, topic: str) -> str:
        """Generates a script based on the given topic."""
        pass

class ImageGenerator(ABC):
    @abstractmethod
    def generate_image(self, prompt: str, output_path: str):
        """Generates an image based on the prompt and saves it to output_path."""
        pass

class VoiceGenerator(ABC):
    @abstractmethod
    def generate_voice(self, text: str, output_path: str):
        """Generates audio from text and saves it to output_path."""
        pass

class VideoEditor(ABC):
    @abstractmethod
    def assemble_video(self, image_paths: List[str], audio_path: str, output_path: str):
        """Assembles video from images and audio."""
        pass
