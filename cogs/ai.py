import nextcord
from nextcord.ext import commands
import httpx
import os
from dotenv import load_dotenv
import asyncio
import aiosqlite
from colorama import Fore, init
from utils.config import GROQ_API_KEY

# Initialize colorama for Windows compatibility
init(autoreset=True)

GROQ_API_KEY = GROQ_API_KEY

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'db/ai_responses.db'
        self.auto_response_enabled = False
        self.message_history = []  # Store up to 5 messages here
        self.setup_db()

    async def setup_db(self):
        """Setup the database and ensure the tables exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS responses
                                (user_id INTEGER, question TEXT, answer TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS guild_settings
                                (guild_id INTEGER, channel_id INTEGER, auto_response_enabled BOOLEAN)''')
            await db.commit()

    async def insert_response(self, user_id, question, answer):
        """Insert a response into the database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('INSERT INTO responses (user_id, question, answer) VALUES (?, ?, ?)',
                             (user_id, question, answer))
            await db.commit()

    async def get_guild_settings(self, guild_id):
        """Fetch the guild settings from the database."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT channel_id, auto_response_enabled FROM guild_settings WHERE guild_id = ?',
                                  (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row
                return None

    async def set_guild_settings(self, guild_id, channel_id, auto_response_enabled):
        """Set the guild settings in the database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''INSERT OR REPLACE INTO guild_settings (guild_id, channel_id, auto_response_enabled)
                                VALUES (?, ?, ?)''', (guild_id, channel_id, auto_response_enabled))
            await db.commit()

    async def ask_ai(self, question: str):
        """Send a request to the AI and return the response."""
        payload = {
            "model": "llama3-8b-8192",
            "messages": [{"role": "user", "content": question}]
        }

        headers = {
            "Content-Type": "application/json", 
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload
                )

                response.raise_for_status()  # Will raise an HTTPStatusError for bad responses
                data = response.json()
                return data['choices'][0]['message']['content']
            except httpx.RequestError as e:
                print(Fore.RED + f"HTTP error occurred: {e}")
                return "An error occurred while processing your request."
            except httpx.HTTPStatusError as e:
                print(Fore.RED + f"HTTP status error: {e}")
                return "Error with API response. Please try again later."

    @nextcord.slash_command(name="askai", description="Ask AI a question and get a response.")
    async def ask_ai_command(self, interaction: nextcord.Interaction, question: str):
        """Slash command to ask AI a question."""
        answer = await self.ask_ai(question)

        if answer:
            await self.insert_response(interaction.user.id, question, answer)

            # Store the question-answer pair in history, ensuring it doesn't exceed 5 items
            self.message_history.append((question, answer))
            if len(self.message_history) > 5:
                self.message_history.pop(0)  # Remove the oldest message

            print(Fore.GREEN + f"[ Ai ]" + Fore.WHITE + f" Successfully sent response message to {Fore.YELLOW}{interaction.user.display_name} ({interaction.user.name})")
            await interaction.response.send_message(f"{answer}")
        else:
            print(Fore.RED + f"[ Ai ] Error processing request for {interaction.user.display_name} ({interaction.user.name})")
            await interaction.response.send_message("There was an error processing your request.")

    @nextcord.slash_command(name="setup", description="Configure auto-response for AI in a specific channel.")
    async def setup(self, interaction: nextcord.Interaction, channel: nextcord.TextChannel, enable: bool):
        """Slash command to enable/disable auto-response for a specific channel."""
        guild_settings = await self.get_guild_settings(interaction.guild.id)

        if guild_settings:
            current_channel_id, current_auto_response = guild_settings
            if current_channel_id != channel.id:
                await interaction.response.send_message(f"Auto-response is not set for this channel. Please configure it in the correct channel.")
                return

        await self.set_guild_settings(interaction.guild.id, channel.id, enable)
        status = "enabled" if enable else "disabled"
        print(Fore.GREEN + f"[ Ai ]" + Fore.WHITE + f" Auto-response {status} for guild {interaction.guild.name} in channel {Fore.YELLOW}{channel.mention}")
        await interaction.response.send_message(f"Auto-response for this guild is now {status} in channel {channel.mention}.")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for messages and provide AI responses if enabled."""
        if message.author.bot:
            return

        guild_settings = await self.get_guild_settings(message.guild.id)

        if guild_settings:
            channel_id, auto_response_enabled = guild_settings
            if message.channel.id != channel_id or not auto_response_enabled:
                return

            answer = await self.ask_ai(message.content)

            if answer:
                await self.insert_response(message.author.id, message.content, answer)
                print(Fore.GREEN + f"[ Ai ]" + Fore.WHITE + f" Successfully sent response message to {Fore.YELLOW}{message.author.display_name} ({message.author.name})")
                await message.channel.send(f"{answer}")
            else:
                print(Fore.RED + f"[ Ai ] Error processing request for {message.author.display_name} ({message.author.name})")
                await message.channel.send("There was an error processing your request.")

def setup(bot):
    if not GROQ_API_KEY:
        print(Fore.YELLOW + "[WARN]: Groq API Key not specified!")
    else:
        bot.add_cog(AICog(bot))