import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# API Keys (Load from environment variables)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "mock-openai-key")
YOUTUBE_CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json")

# Output Directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Application Settings
VIDEO_RESOLUTION = (1080, 1920) # Shorts format (9:16)
DEFAULT_DURATION = 15 # seconds
LOOP_INTERVAL = int(os.getenv("LOOP_INTERVAL", 60)) # seconds
