import nextcord
from nextcord.ext import commands
from groq import Groq
import sqlite3
import logging
import json
import asyncio
from typing import Optional
from pathlib import Path
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "ai_bot.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self) -> None:
        """Initialize the database with required tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_history (
                    message_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    user_id INTEGER,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
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
        """Load configuration from JSON file."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self._config = json.load(f)
        else:
            self._config = {
                "model": "llama3-8b-8192",
                "max_retries": 3,
                "retry_delay": 1,
                "message_timeout": 60,
                "max_history": 10
            }
            self.save_config()

    def save_config(self) -> None:
        """Save current configuration to JSON file."""
        with open(self.config_path, 'w') as f:
            json.dump(self._config, f, indent=4)

    def get(self, key: str, default=None):
        """Get configuration value."""
        return self._config.get(key, default)

class AICog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
        self.config = Config()
        self.groq_client = Groq()
        self.message_cache = {}

    async def generate_ai_response(self, prompt: str, retry_count: int = 0) -> Optional[str]:
        """Generate AI response with retry logic."""
        max_retries = self.config.get("max_retries", 3)
        retry_delay = self.config.get("retry_delay", 1)

        try:
            chat_completion = await asyncio.to_thread(
                self.groq_client.chat.completions.create,
                messages=[{"role": "user", "content": prompt}],
                model=self.config.get("model", "llama3-8b-8192"),
                stream=False
            )
            return chat_completion.choices[0].message.content

        except Exception as e:
            if retry_count < max_retries:
                logger.warning(f"AI response generation failed, retrying... ({retry_count + 1}/{max_retries})")
                await asyncio.sleep(retry_delay)
                return await self.generate_ai_response(prompt, retry_count + 1)
            else:
                logger.error(f"Failed to generate AI response after {max_retries} attempts: {str(e)}")
                raise

    @nextcord.slash_command(
        name="setup",
        description="Set up a channel for AI responses"
    )
    @commands.has_permissions(administrator=True)
    async def setup(self, interaction: nextcord.Interaction):
        """Set up AI response channel with proper error handling."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO ai_channels (guild_id, channel_id)
                       VALUES (?, ?)
                       ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?""",
                    (interaction.guild_id, interaction.channel_id, interaction.channel_id)
                )
                conn.commit()

            await interaction.response.send_message(
                f"✅ AI responses enabled in {interaction.channel.mention}",
                ephemeral=True
            )
            logger.info(f"AI channel set up in guild {interaction.guild_id}")

        except Exception as e:
            logger.error(f"Setup failed for guild {interaction.guild_id}: {str(e)}")
            await interaction.response.send_message(
                "❌ Failed to set up AI channel. Please try again later.",
                ephemeral=True
            )

    @nextcord.slash_command(
        name="config",
        description="View or modify bot configuration"
    )
    @commands.has_permissions(administrator=True)
    async def config_command(self, interaction: nextcord.Interaction, key: str = None, value: str = None):
        """View or modify bot configuration."""
        if not key:
            config_text = "\n".join(f"{k}: {v}" for k, v in self._config._config.items())
            await interaction.response.send_message(f"Current configuration:\n```\n{config_text}\n```")
            return

        if value is None:
            current_value = self.config.get(key)
            await interaction.response.send_message(f"Current value of {key}: {current_value}")
        else:
            try:
                self.config._config[key] = value
                self.config.save_config()
                await interaction.response.send_message(f"✅ Updated {key} to: {value}")
            except Exception as e:
                await interaction.response.send_message(f"❌ Failed to update configuration: {str(e)}")

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message):
        """Handle incoming messages with improved error handling and rate limiting."""
        if message.author.bot:
            return

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT channel_id FROM ai_channels WHERE guild_id = ?",
                    (message.guild.id,)
                )
                result = cursor.fetchone()

                if not result or message.channel.id != result[0]:
                    return

            # Store message in history
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO message_history (message_id, guild_id, user_id, content)
                       VALUES (?, ?, ?, ?)""",
                    (message.id, message.guild.id, message.author.id, message.content)
                )
                conn.commit()

            async with message.channel.typing():
                response = await self.generate_ai_response(message.content)
                if response:
                    await message.reply(response)
                    logger.info(f"Successfully responded to message {message.id} in guild {message.guild.id}")

        except Exception as e:
            logger.error(f"Error processing message {message.id}: {str(e)}")
            await message.channel.send(
                "❌ I encountered an error processing your message. Please try again later."
            )

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Global error handler for commands."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Please wait {error.retry_after:.1f}s before using this command again.")
        else:
            logger.error(f"Command error: {str(error)}")
            await ctx.send("❌ An error occurred while processing your command.")

def setup(bot: commands.Bot):
    """Set up the cog with the bot."""
    bot.add_cog(AICog(bot))
