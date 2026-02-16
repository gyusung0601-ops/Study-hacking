from moviepy import ImageClip, AudioFileClip
from video_automation.interfaces import VideoEditor
from typing import List

class SimpleVideoEditor(VideoEditor):
    def assemble_video(self, image_paths: List[str], audio_path: str, output_path: str):
        # Load audio
        try:
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration

            # Load image(s)
            image_clip = ImageClip(image_paths[0])

            # Set duration
            image_clip = image_clip.with_duration(duration)

            # Set audio
            video_clip = image_clip.with_audio(audio_clip)

            # Write output
            video_clip.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')
            print(f"Video assembled at {output_path}")

        except Exception as e:
            print(f"Error assembling video: {e}")
            raise e
