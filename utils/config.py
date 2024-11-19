from dotenv import load_dotenv
import os

load_dotenv()
BOT_TOKEN = "" # your bot token
OWNER_ID = ""
GROQ_API_KEY = ""
if not GROQ_API_KEY:
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not OWNER_ID:
    OWNER_ID = os.getenv('OWNER_ID')
if not BOT_TOKEN:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
