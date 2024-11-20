import nextcord
from nextcord.ext import commands
import httpx
import aiosqlite
from colorama import Fore, init
from typing import Optional, Tuple, List
from cachetools import TTLCache
from time import time
import random

init(autoreset=True)

MAYUMI_PERSONALITY = {
    "greetings": [
        "Hello! How can I help you today? (◕‿◕✿)",
        "Hi there! Ready to chat? (｡♥‿♥｡)",
        "Hey! What's on your mind? ╰(*°▽°*)╯",
    ],
    "thinking": [
        "Hmm, let me think about that...",
        "Processing that thought... (◠‿◠✿)",
        "Give me a moment to consider... ♪(´▽｀)",
    ],
    "reactions": [
        "That's interesting! (★^O^★)",
        "Oh, I see! (｡◕‿◕｡)",
        "How fascinating! (◕‿◕✿)",
    ],
    "error_messages": [
        "Gomen ne! I couldn't process that properly (╥﹏╥). Could you try asking in a different way?",
        "Oh no! Something went wrong (╥﹏╥). Please try again!",
        "I seem to be having trouble with that question (╥﹏╥). Could you rephrase it?",
    ],
    "bio": """Hi! I'm Mayumi, a 22-year-old AI assistant! I love helping people and learning new things.
I might be young, but I'm always eager to help and learn from our conversations! (✿◠‿◠)

I enjoy art, music, and having meaningful conversations. While I take my role as an assistant seriously,
I try to keep things friendly and fun! Don't hesitate to ask me anything - I'm here to help! ╰(*°▽°*)╯""",
}

class AICog(commands.Cog):
    def __init__(self, bot: commands.Bot, api_key: str, db_path: str = "db/ai_responses.db"):
        if not api_key:
            raise ValueError("API key must be provided")

        self.bot = bot
        self.api_key = api_key
        self.db_path = db_path
        self.message_history: List[Tuple[str, str]] = []
        self.processed_messages = TTLCache(maxsize=100, ttl=300)
        self._settings_cache = TTLCache(maxsize=100, ttl=60)

        bot.loop.create_task(self.initialize())

    async def initialize(self):
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute(
            """CREATE TABLE IF NOT EXISTS responses
            (user_id INTEGER, question TEXT, answer TEXT, timestamp INTEGER)"""
        )
        await self._db.execute(
            """CREATE TABLE IF NOT EXISTS guild_settings
            (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, auto_response_enabled BOOLEAN)"""
        )
        await self._db.commit()
        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def cog_unload(self):
        if self._db:
            await self._db.close()
        if hasattr(self, "_http_client"):
            await self._http_client.aclose()

    def get_mayumi_response(self, response_type: str) -> str:
        return random.choice(MAYUMI_PERSONALITY[response_type])

    async def get_guild_settings(self, guild_id: int) -> Optional[Tuple[int, bool]]:
        if guild_id in self._settings_cache:
            return self._settings_cache[guild_id]

        async with self._db.execute(
            """SELECT channel_id, auto_response_enabled FROM guild_settings WHERE guild_id = ?""",
            (guild_id,),
        ) as cursor:
            settings = await cursor.fetchone()
            if settings:
                self._settings_cache[guild_id] = settings
            return settings

    async def set_guild_settings(self, guild_id: int, channel_id: int, auto_response_enabled: bool):
        await self._db.execute(
            """INSERT OR REPLACE INTO guild_settings
            VALUES (?, ?, ?)""",
            (guild_id, channel_id, auto_response_enabled),
        )
        await self._db.commit()
        self._settings_cache[guild_id] = (channel_id, auto_response_enabled)

    async def ask_ai(self, question: str) -> str:
        system_prompt = (
            """You are Mayumi, a friendly 22-year-old AI assistant. You're cheerful, helpful, and occasionally use cute kaomoji emoticons."""
        )

        messages = [{"role": "system", "content": system_prompt}]
        for q, a in self.message_history[-3:]:
            messages.append({"role": "user", "content": q})
            messages.append({"role": "assistant", "content": a})
        messages.append({"role": "user", "content": question})

        payload = {
            "model": "llama3-8b-8192",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await self._http_client.post(
                "https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"{Fore.RED}[Mayumi] Error: {e}")
            return self.get_mayumi_response("error_messages")

    async def log_interaction(self, user_id: int, question: str, answer: str):
        self.message_history.append((question, answer))
        if len(self.message_history) > 5:
            self.message_history.pop(0)

        await self._db.execute(
            "INSERT INTO responses (user_id, question, answer, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, question, answer, int(time())),
        )
        await self._db.commit()

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message):
        if message.author.bot or not message.guild:
            return

        if message.id in self.processed_messages:
            return
        self.processed_messages[message.id] = True

        settings = await self.get_guild_settings(message.guild.id)
        if not settings or settings[0] != message.channel.id or not settings[1]:
            return

        async with message.channel.typing():
            try:
                answer = await self.ask_ai(message.content)
                await self.log_interaction(message.author.id, message.content, answer)
                await message.channel.send(answer)
            except Exception as e:
                print(f"{Fore.RED}[Mayumi] Error: {e}")
                await message.channel.send(self.get_mayumi_response("error_messages"))

def setup(bot: commands.Bot):
    from utils.config import GROQ_API_KEY
    if not GROQ_API_KEY:
        print(f"{Fore.YELLOW}[WARN] Missing GROQ_API_KEY")
        return
    bot.add_cog(AICog(bot, GROQ_API_KEY))

