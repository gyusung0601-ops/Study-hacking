import os
import random
import requests
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from video_automation.interfaces import ScriptGenerator, ImageGenerator, VoiceGenerator
from video_automation.config import OPENAI_API_KEY

try:
    import openai
except ImportError:
    openai = None

class SimpleScriptGenerator(ScriptGenerator):
    def __init__(self):
        self.topics = {
            "Fun Fact": [
                "Honey never spoils. Archaeologists have found pots of honey in ancient Egyptian tombs that are over 3,000 years old and still perfectly edible.",
                "Octopuses have three hearts. Two pump blood to the gills, while one pumps it to the rest of the body.",
                "Bananas are curved because they grow towards the sun. This process is called negative geotropism."
            ],
            "Meditation": [
                "Take a deep breath. Inhale... Exhale... Let go of your stress and focus on the present moment.",
                "Visualize a calm ocean. The waves are gently rolling in. You are at peace."
            ],
            "Scary Story": [
                "I heard a tap on the window. I live on the 14th floor...",
                "The baby monitor clearly heard a voice say 'goodnight', but I live alone."
            ]
        }
        self.client = None
        if openai and OPENAI_API_KEY and OPENAI_API_KEY != "mock-openai-key":
            self.client = openai.OpenAI(api_key=OPENAI_API_KEY)

    def generate_script(self, topic: str) -> str:
        if self.client:
            try:
                print(f"Generating script for topic '{topic}' using OpenAI...")
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a creative writer for short form videos."},
                        {"role": "user", "content": f"Write a short, engaging script for a video about {topic}. Keep it under 50 words."}
                    ]
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"OpenAI API Error: {e}. Falling back to mock generator.")

        # Fallback to mock logic
        if topic in self.topics:
            return random.choice(self.topics[topic])
        else:
            return f"This is a default script regarding {topic} because the topic was not found in the mock database."

class SimpleImageGenerator(ImageGenerator):
    def __init__(self):
        self.font_path = os.path.join(os.path.dirname(__file__), "fonts", "Roboto-Bold.ttf")
        self._ensure_font()

    def _ensure_font(self):
        if not os.path.exists(self.font_path):
            os.makedirs(os.path.dirname(self.font_path), exist_ok=True)
            # URL to a reliable font source (Google Fonts repo)
            url = "https://raw.githubusercontent.com/googlefonts/roboto-2/main/src/hinted/Roboto-Bold.ttf"
            print(f"Downloading font from {url}...")
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    with open(self.font_path, "wb") as f:
                        f.write(response.content)
                    print("Font downloaded.")
                else:
                    print(f"Failed to download font. Status code: {response.status_code}")
            except Exception as e:
                print(f"Error downloading font: {e}")

    def generate_image(self, prompt: str, output_path: str):
        # Generate a random color background image with text
        width, height = 1080, 1920
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        img = Image.new('RGB', (width, height), color=color)

        d = ImageDraw.Draw(img)

        # Try to load downloaded font, otherwise fallback
        try:
            font = ImageFont.truetype(self.font_path, 60)
        except IOError:
            print("Could not load custom font, falling back to default.")
            font = ImageFont.load_default()

        # Simple text wrapping (very basic)
        margin = 100
        offset = 400
        # If prompt is long, truncate it for the image or split it
        # Just taking first 100 chars for image text to avoid overflow
        display_text = prompt[:200] + "..." if len(prompt) > 200 else prompt

        # Split by simple logic
        words = display_text.split()
        current_line = ""
        lines = []
        for word in words:
            if len(current_line) + len(word) < 20: # simple width check
                current_line += word + " "
            else:
                lines.append(current_line)
                current_line = word + " "
        lines.append(current_line)

        for line in lines:
            d.text((margin, offset), line.strip(), font=font, fill=(255, 255, 255))
            offset += 100

        img.save(output_path)
        print(f"Generated image at {output_path}")

class SimpleVoiceGenerator(VoiceGenerator):
    def generate_voice(self, text: str, output_path: str):
        tts = gTTS(text=text, lang='en')
        tts.save(output_path)
        print(f"Generated voice at {output_path}")
