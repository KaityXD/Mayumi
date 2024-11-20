import nextcord
from nextcord.ext import commands
from nextcord import Embed
import sqlite3
import os
import typing
from pathlib import Path

class StarboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = Path("db/starboard.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.setup_database()

    def setup_database(self):
        """Initialize the SQLite database and create required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Table for starboard configuration
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    threshold INTEGER DEFAULT 3
                )
            ''')

            # Table for starred messages
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS starred_messages (
                    original_message_id INTEGER PRIMARY KEY,
                    starboard_message_id INTEGER,
                    guild_id INTEGER,
                    star_count INTEGER DEFAULT 0,
                    FOREIGN KEY (guild_id) REFERENCES config(guild_id)
                )
            ''')

            conn.commit()

    def get_config(self, guild_id: int) -> tuple[int, int]:
        """Get starboard configuration for a guild."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT channel_id, threshold FROM config WHERE guild_id = ?",
                (guild_id,)
            )
            result = cursor.fetchone()
            return result if result else (None, 3)

    def update_star_count(self, message_id: int, guild_id: int, count: int):
        """Update star count for a message."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO starred_messages (original_message_id, guild_id, star_count)
                VALUES (?, ?, ?)
                ON CONFLICT(original_message_id) 
                DO UPDATE SET star_count = ?
            ''', (message_id, guild_id, count, count))
            conn.commit()

    def get_starboard_message_id(self, original_message_id: int) -> int:
        """Get the starboard message ID for an original message."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT starboard_message_id FROM starred_messages WHERE original_message_id = ?",
                (original_message_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def set_starboard_message_id(self, original_message_id: int, starboard_message_id: int):
        """Set the starboard message ID for an original message."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE starred_messages 
                SET starboard_message_id = ? 
                WHERE original_message_id = ?
            ''', (starboard_message_id, original_message_id))
            conn.commit()

    def remove_starred_message(self, message_id: int):
        """Remove a message from the starboard database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM starred_messages WHERE original_message_id = ?",
                (message_id,)
            )
            conn.commit()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: nextcord.RawReactionActionEvent):
        if str(payload.emoji) == "⭐":
            await self.process_star_reaction(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: nextcord.RawReactionActionEvent):
        if str(payload.emoji) == "⭐":
            await self.process_star_reaction(payload, removed=True)

    async def process_star_reaction(self, payload: nextcord.RawReactionActionEvent, removed: bool = False):
        if not (guild := self.bot.get_guild(payload.guild_id)):
            return

        channel_id, threshold = self.get_config(guild.id)
        if not channel_id:
            return

        if not (starboard_channel := guild.get_channel(channel_id)):
            return

        if not (channel := guild.get_channel(payload.channel_id)):
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except nextcord.NotFound:
            return

        if message.author.bot or channel.id == channel_id:
            return

        star_count = sum(1 for reaction in message.reactions 
                        if str(reaction.emoji) == "⭐")

        self.update_star_count(message.id, guild.id, star_count)

        if star_count >= threshold:
            await self.add_to_starboard(message, starboard_channel)
        elif star_count < threshold:
            await self.remove_from_starboard(message, starboard_channel)

    async def add_to_starboard(self, message: nextcord.Message, 
                             starboard_channel: nextcord.TextChannel) -> None:
        starboard_message_id = self.get_starboard_message_id(message.id)

        if starboard_message_id:
            try:
                starboard_message = await starboard_channel.fetch_message(starboard_message_id)
                embed = self.create_starboard_embed(message)
                await starboard_message.edit(embed=embed)
                return
            except nextcord.NotFound:
                pass

        embed = self.create_starboard_embed(message)
        starboard_message = await starboard_channel.send(embed=embed)
        self.set_starboard_message_id(message.id, starboard_message.id)

    def create_starboard_embed(self, message: nextcord.Message) -> Embed:
        embed = Embed(
            description=message.content or "[No Text]",
            color=nextcord.Color.gold(),
            timestamp=message.created_at
        )

        avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url

        embed.set_author(name=message.author.display_name, icon_url=avatar_url)
        embed.add_field(
            name="Source",
            value=f"[Jump to message]({message.jump_url}) in {message.channel.mention}"
        )

        if message.attachments:
            if len(message.attachments) > 1:
                embed.add_field(
                    name="Additional Attachments",
                    value=f"This message has {len(message.attachments)} attachments",
                    inline=False
                )
            embed.set_image(url=message.attachments[0].url)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT star_count FROM starred_messages WHERE original_message_id = ?",
                (message.id,)
            )
            star_count = cursor.fetchone()[0]

        embed.set_footer(
            text=f"⭐ {star_count} | Message ID: {message.id}"
        )

        return embed

    async def remove_from_starboard(self, message: nextcord.Message, 
                                  starboard_channel: nextcord.TextChannel) -> None:
        starboard_message_id = self.get_starboard_message_id(message.id)

        if starboard_message_id:
            try:
                starboard_message = await starboard_channel.fetch_message(starboard_message_id)
                await starboard_message.delete()
                self.remove_starred_message(message.id)
            except nextcord.NotFound:
                pass

    @nextcord.slash_command(name="starboard", description="Manage starboard settings")
    async def starboard(self, interaction: nextcord.Interaction):
        pass

    @starboard.subcommand(name="channel", description="Set the starboard channel")
    @commands.has_permissions(manage_channels=True)
    async def starboard_channel(self, interaction: nextcord.Interaction, channel: nextcord.TextChannel):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO config (guild_id, channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) 
                DO UPDATE SET channel_id = ?
            ''', (interaction.guild_id, channel.id, channel.id))
            conn.commit()

        await interaction.response.send_message(f"✅ Starboard channel set to {channel.mention}")

    @starboard.subcommand(name="threshold", description="Set the number of stars required")
    @commands.has_permissions(manage_channels=True)
    async def starboard_threshold(self, interaction: nextcord.Interaction, stars: int):
        if stars < 1:
            await interaction.response.send_message("❌ Star threshold must be at least 1.", ephemeral=True)
            return

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO config (guild_id, threshold)
                VALUES (?, ?)
                ON CONFLICT(guild_id) 
                DO UPDATE SET threshold = ?
            ''', (interaction.guild_id, stars, stars))
            conn.commit()

        await interaction.response.send_message(f"✅ Star threshold set to {stars} stars")

def setup(bot):
    bot.add_cog(StarboardCog(bot))
