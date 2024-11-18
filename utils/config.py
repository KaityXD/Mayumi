from dotenv import load_dotenv
import os

load_dotenv()
BOT_TOKEN = "" # your bot token
if not BOT_TOKEN:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
