import os
import random
import time
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class YouTubeManager:
    def __init__(self, client_secrets_file: str):
        self.client_secrets_file = client_secrets_file
        self.youtube = None
        self.authenticated = False
        self.scopes = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]

    def authenticate(self):
        """Authenticates with YouTube API."""
        if os.path.exists(self.client_secrets_file):
            print(f"Authenticating with {self.client_secrets_file}...")
            creds = None
            # check for token.pickle
            if os.path.exists("token.pickle"):
                try:
                    with open("token.pickle", "rb") as token:
                        creds = pickle.load(token)
                except Exception:
                    creds = None

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.client_secrets_file, self.scopes)
                    # This requires user interaction
                    try:
                         # Attempt to open browser for auth
                         creds = flow.run_local_server(port=0)
                    except OSError:
                         # Fallback for headless environments (console based auth)
                         creds = flow.run_console()

                # Save credentials
                with open("token.pickle", "wb") as token:
                    pickle.dump(creds, token)

            self.youtube = build("youtube", "v3", credentials=creds)
            self.authenticated = True
            print("Authentication successful.")
        else:
            print("Client secrets file not found. Using Mock mode.")
            self.authenticated = False

    def upload_video(self, file_path: str, title: str, description: str, tags: list, category_id: str = "22", privacy_status: str = "private"):
        """Uploads video to YouTube."""
        if not self.youtube and not self.authenticated:
             self.authenticate()

        if self.youtube:
            print(f"Uploading video {file_path} to YouTube...")
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": category_id
                },
                "status": {
                    "privacyStatus": privacy_status
                }
            }

            media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"Uploaded {int(status.progress() * 100)}%")

            print(f"Upload complete! Video ID: {response['id']}")
            return response['id']

        else:
            # Mock Logic
            print(f"[MOCK] Uploading video {file_path}...")
            time.sleep(1)
            video_id = f"mock_vid_{int(time.time())}"
            print(f"[MOCK] Upload complete! Video ID: {video_id}")
            return video_id

    def get_video_stats(self, video_id: str):
        """Retrieves video statistics."""
        if not self.youtube and not self.authenticated:
             self.authenticate()

        if self.youtube and not video_id.startswith("mock_"):
            try:
                request = self.youtube.videos().list(
                    part="statistics",
                    id=video_id
                )
                response = request.execute()
                if "items" in response and len(response["items"]) > 0:
                    stats = response["items"][0]["statistics"]
                    # Convert strings to ints
                    return {
                        "viewCount": int(stats.get("viewCount", 0)),
                        "likeCount": int(stats.get("likeCount", 0)),
                        "commentCount": int(stats.get("commentCount", 0))
                    }
                return {}
            except Exception as e:
                print(f"Error fetching stats: {e}")
                return {}
        else:
            # Mock Logic
            print(f"[MOCK] Fetching stats for video {video_id}...")
            views = random.randint(0, 10000)
            stats = {
                "viewCount": views,
                "likeCount": int(views * 0.05),
                "commentCount": int(views * 0.01)
            }
            print(f"[MOCK] Stats: {stats}")
            return stats
