import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'ai_meeting_assistant.db')}"

APP_NAME = os.getenv("APP_NAME", "AI Meeting Assistant")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRATION = int(os.getenv("ACCESS_TOKEN_EXPIRATION", 30))
