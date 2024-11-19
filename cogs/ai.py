import nextcord
from nextcord.ext import commands
import sqlite3
import json
import asyncio
import httpx
import os
from typing import Optional
from pathlib import Path
from contextlib import contextmanager

class DatabaseManager:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.setup_database()

    def setup_database(self) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_history (
                    message_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

class Config:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.load_config()

    def load_config(self) -> None:
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self._config = json.load(f)
        else:
            self._config = {
                "model": "llama3-8b-8192",
                "max_retries": 3,
                "retry_delay": 1,
                "message_timeout": 60,
                "max_history": 10,
                "bot_name": "Luna",
                "bot_personalities": {
                    "default": "You are Luna, a friendly and helpful AI assistant.",
                    "professional": "You are Luna, a professional and efficient AI assistant focused on business matters.",
                    "casual": "You are Luna, a casual and fun AI chatbot who loves making friends."
                }
            }
            self.save_config()

    def save_config(self) -> None:
        with open(self.config_path, 'w') as f:
            json.dump(self._config, f, indent=4)

    def get(self, key: str, default=None):
        return self._config.get(key, default)

class GroqAPI:
    def __init__(self):
        self.api_key = os.getenv('GROQ_API_KEY')
        self.client = httpx.AsyncClient()
        self.base_url = "https://api.groq.com/v1/completions"

    async def generate_completion(self, prompt: str, model: str) -> Optional[str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "prompt": prompt,
            "max_tokens": 1000,
            "temperature": 0.7
        }

        try:
            async with self.client as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=data,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()["choices"][0]["text"].strip()
        except Exception:
            return None

class AICog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
        self.config = Config()
        self.groq_api = GroqAPI()
        self.message_cache = {}
        self.current_personality = "default"

    @nextcord.slash_command(
        name="setchannel",
        description="Set the AI channel for this server"
    )
    @commands.has_permissions(administrator=True)
    async def set_channel(self, interaction: nextcord.Interaction, channel: nextcord.TextChannel):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO ai_channels (guild_id, channel_id) VALUES (?, ?)",
                (interaction.guild_id, channel.id)
            )
            conn.commit()
        await interaction.response.send_message(
            f"AI channel set to {channel.mention}",
            ephemeral=True
        )

    @nextcord.slash_command(
        name="rename",
        description="Change the bot's name"
    )
    @commands.has_permissions(administrator=True)
    async def rename(self, interaction: nextcord.Interaction, new_name: str):
        try:
            await interaction.guild.me.edit(nick=new_name)
            self.config._config["bot_name"] = new_name
            self.config.save_config()
            await interaction.response.send_message(
                f"✅ I've been renamed to {new_name}!",
                ephemeral=True
            )
        except Exception:
            await interaction.response.send_message(
                "❌ Failed to change my name. Please check permissions.",
                ephemeral=True
            )

    @nextcord.slash_command(
        name="personality",
        description="Change the bot's personality"
    )
    @commands.has_permissions(administrator=True)
    async def change_personality(
        self,
        interaction: nextcord.Interaction,
        personality: str = nextcord.SlashOption(
            name="type",
            choices=["default", "professional", "casual"],
            description="Choose the bot's personality"
        )
    ):
        try:
            self.current_personality = personality
            await interaction.response.send_message(
                f"✅ Personality changed to: {personality}",
                ephemeral=True
            )
        except Exception:
            await interaction.response.send_message(
                "❌ Failed to change personality",
                ephemeral=True
            )

    async def generate_ai_response(self, prompt: str, retry_count: int = 0) -> Optional[str]:
        personality = self.config.get("bot_personalities", {}).get(
            self.current_personality,
            self.config.get("bot_personalities", {}).get("default", "")
        )
        contextualized_prompt = f"{personality}\n\nUser: {prompt}"

        try:
            response = await self.groq_api.generate_completion(
                prompt=contextualized_prompt,
                model=self.config.get("model", "llama3-8b-8192")
            )
            if response:
                return response
            
            if retry_count < self.config.get("max_retries", 3):
                await asyncio.sleep(self.config.get("retry_delay", 1))
                return await self.generate_ai_response(prompt, retry_count + 1)
            return "I'm having trouble generating a response. Please try again later."
            
        except Exception:
            return None

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message):
        if message.author.bot:
            return

        bot_name = self.config.get("bot_name", "Luna")
        should_respond = False
        response_prefix = ""

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT channel_id FROM ai_channels WHERE guild_id = ?",
                    (message.guild.id,)
                )
                result = cursor.fetchone()

                if (result and message.channel.id == result[0]) or \
                   (self.bot.user in message.mentions) or \
                   (message.content.lower().startswith(bot_name.lower())):
                    should_respond = True

                    if message.content.lower().startswith(bot_name.lower()):
                        message.content = message.content[len(bot_name):].strip()
                        response_prefix = f"*{bot_name}:* "

            if should_respond:
                async with message.channel.typing():
                    response = await self.generate_ai_response(message.content)
                    if response:
                        full_response = f"{response_prefix}{response}" if response_prefix else response
                        await message.reply(full_response)

        except Exception:
            await message.channel.send(
                "❌ An error occurred. Please try again later."
            )

def setup(bot: commands.Bot):
    bot.add_cog(AICog(bot))
