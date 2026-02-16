import os
import time
from video_automation.config import *
from video_automation.generators import SimpleScriptGenerator, SimpleImageGenerator, SimpleVoiceGenerator
from video_automation.editor import SimpleVideoEditor
from video_automation.youtube_client import YouTubeManager

def main():
    print("Starting Video Automation System...")
    print(f"Loop Interval: {LOOP_INTERVAL} seconds")

    # 1. Initialize Components
    script_gen = SimpleScriptGenerator()
    image_gen = SimpleImageGenerator()
    voice_gen = SimpleVoiceGenerator()
    editor = SimpleVideoEditor()
    yt_manager = YouTubeManager(YOUTUBE_CLIENT_SECRETS_FILE)

    # Simple Loop for MVP
    topics = ["Fun Fact", "Meditation", "Scary Story"]

    # Simulated Feedback Loop state
    current_topic_index = 0

    while True:
        try:
            current_topic = topics[current_topic_index]
            print(f"\n--- Starting Cycle for Topic: {current_topic} ---")

            # 2. Generate Script
            script = script_gen.generate_script(current_topic)
            print(f"Generated Script: {script}")

            # 3. Generate Assets
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            timestamp = int(time.time())
            image_path = os.path.join(OUTPUT_DIR, f"background_{timestamp}.png")
            audio_path = os.path.join(OUTPUT_DIR, f"audio_{timestamp}.mp3")
            video_path = os.path.join(OUTPUT_DIR, f"final_video_{timestamp}.mp4")

            image_gen.generate_image(script, image_path)
            voice_gen.generate_voice(script, audio_path)

            # 4. Assemble Video
            # Ensure paths exist before assembling
            if os.path.exists(image_path) and os.path.exists(audio_path):
                editor.assemble_video([image_path], audio_path, video_path)

                # 5. Upload Video
                if os.path.exists(video_path):
                    video_id = yt_manager.upload_video(
                        video_path,
                        title=f"Daily {current_topic} Video",
                        description=script,
                        tags=["#shorts", "#ai", "#automation"]
                    )

                    # 6. Feedback Loop Simulation
                    # Note: In a real-world scenario, you would track video_ids in a database
                    # and check their stats after 24-48 hours.
                    # Here, we check immediately for demonstration (mock logic simulates views).
                    stats = yt_manager.get_video_stats(video_id)
                    views = stats.get("viewCount", 0)

                    print(f"Video {video_id} has {views} views.")

                    if views > 5000:
                        print("High views! Keeping topic strategy.")
                    else:
                        print("Low views. Switching topic for next run.")
                        current_topic_index = (current_topic_index + 1) % len(topics)
                else:
                    print("Error: Video file failed to generate.")
            else:
                print("Error: Asset generation failed.")

        except Exception as e:
            print(f"An error occurred in the loop: {e}")
            import traceback
            traceback.print_exc()

        print(f"Sleeping for {LOOP_INTERVAL} seconds...")
        time.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    main()
