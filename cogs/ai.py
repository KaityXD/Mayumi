import nextcord
from nextcord.ext import commands
import httpx
import aiosqlite
from colorama import Fore, init
from typing import Optional, Tuple, List
import asyncio
from functools import lru_cache

init(autoreset=True)

class AICog(commands.Cog):
    def __init__(self, bot: commands.Bot, api_key: str, db_path: str = 'db/ai_responses.db'):
        if not api_key:
            raise ValueError("API key must be provided")
        self.bot = bot
        self.api_key = api_key
        self.db_path = db_path
        self.message_history: List[Tuple[str, str]] = []
        self._db = None
        self._http_client = None
        bot.loop.create_task(self.initialize())

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute('''CREATE TABLE IF NOT EXISTS responses
                              (user_id INTEGER, question TEXT, answer TEXT)''')
        await self._db.execute('''CREATE TABLE IF NOT EXISTS guild_settings
                              (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, auto_response_enabled BOOLEAN)''')
        await self._db.commit()
        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def cog_unload(self) -> None:
        if self._db:
            await self._db.close()
        if self._http_client:
            await self._http_client.aclose()

    @lru_cache(maxsize=100)
    async def get_guild_settings(self, guild_id: int) -> Optional[Tuple[int, bool]]:
        async with self._db.execute(
            'SELECT channel_id, auto_response_enabled FROM guild_settings WHERE guild_id = ?',
            (guild_id,)
        ) as cursor:
            return await cursor.fetchone()

    async def set_guild_settings(self, guild_id: int, channel_id: int, auto_response_enabled: bool) -> None:
        await self._db.execute(
            'INSERT OR REPLACE INTO guild_settings VALUES (?, ?, ?)',
            (guild_id, channel_id, auto_response_enabled)
        )
        await self._db.commit()
        self.get_guild_settings.cache_clear()

    async def ask_ai(self, question: str) -> str:
        payload = {
            "model": "llama3-8b-8192",
            "messages": [{"role": "user", "content": question}] + [
                {"role": "assistant" if i % 2 else "user", "content": msg}
                for prev_q, prev_a in self.message_history[-3:]
                for i, msg in enumerate([prev_q, prev_a])
            ]
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            response = await self._http_client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"{Fore.RED}Error in ask_ai: {str(e)}")
            raise

    async def log_interaction(self, user_id: int, question: str, answer: str) -> None:
        self.message_history.append((question, answer))
        if len(self.message_history) > 5:
            self.message_history.pop(0)
        
        await self._db.execute(
            'INSERT INTO responses VALUES (?, ?, ?)',
            (user_id, question, answer)
        )
        await self._db.commit()

    @nextcord.slash_command(name="askai", description="Ask AI a question")
    async def ask_ai_command(self, interaction: nextcord.Interaction, question: str):
        await interaction.response.defer()
        
        try:
            answer = await self.ask_ai(question)
            await self.log_interaction(interaction.user.id, question, answer)
            print(f"{Fore.GREEN}[AI] Response sent to {interaction.user.display_name}")
            await interaction.followup.send(answer)
        except Exception as e:
            print(f"{Fore.RED}[AI] Error: {str(e)}")
            await interaction.followup.send("An error occurred. Please try again later.")

    @nextcord.slash_command(name="setup", description="Configure AI auto-response")
    async def setup(self, interaction: nextcord.Interaction, channel: nextcord.TextChannel, enable: bool):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions.")
            return

        await self.set_guild_settings(interaction.guild.id, channel.id, enable)
        status = "enabled" if enable else "disabled"
        await interaction.response.send_message(
            f"Auto-response {status} in {channel.mention}"
        )

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message):
        if message.author.bot or not message.guild:
            return

        settings = await self.get_guild_settings(message.guild.id)
        if not settings or settings[0] != message.channel.id or not settings[1]:
            return

        try:
            answer = await self.ask_ai(message.content)
            await self.log_interaction(message.author.id, message.content, answer)
            await message.channel.send(answer)
        except Exception as e:
            print(f"{Fore.RED}[AI] Error in auto-response: {str(e)}")

def setup(bot: commands.Bot):
    from utils.config import GROQ_API_KEY
    if not GROQ_API_KEY:
        print(f"{Fore.YELLOW}[WARN] Missing GROQ_API_KEY")
        return
    bot.add_cog(AICog(bot, GROQ_API_KEY))
