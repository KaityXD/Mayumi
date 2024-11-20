from dotenv import load_dotenv
import os

load_dotenv()
# <<<<<<< HEAD
BOT_TOKEN = "" # your bot token
OWNER_ID = 1118160684119752834
GROQ_API_KEY = "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"

# For music cog
LAVALINK_HOST = "lava-v4.ajieblogs.eu.org"
LAVALINK_PORT = 80
LAVALINK_PASSWORD = "https://dsc.gg/ajidevserver"


if not GROQ_API_KEY:
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not OWNER_ID:
    OWNER_ID = os.getenv('OWNER_ID')
if not BOT_TOKEN:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
