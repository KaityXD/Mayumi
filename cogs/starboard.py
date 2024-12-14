import nextcord
from nextcord.ext import commands
import sqlite3
from typing import Optional
import re
import aiohttp

class StarboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('db/starboard.db')
        self.create_tables()
        # Supported media extensions
        self.media_extensions = ['.gif', '.png', '.jpg', '.jpeg', '.webp', '.webm', '.mp4', '.mov']

    def create_tables(self):
        """Initialize database tables for starboard system."""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS starboard_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                star_threshold INTEGER DEFAULT 3,
                self_star_allowed BOOLEAN DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS starred_messages (
                message_id INTEGER PRIMARY KEY,
                guild_id INTEGER,
                original_channel_id INTEGER,
                starboard_message_id INTEGER,
                star_count INTEGER DEFAULT 1,
                original_author_id INTEGER,
                media_url TEXT
            )
        ''')
        self.conn.commit()

    def extract_media_url(self, message):
        """Extract media URL from message attachments or links."""
        # Check attachments first
        if message.attachments:
            attachment = message.attachments[0]
            return attachment.url

        # Check for media links in message content
        for word in message.content.split():
            if any(word.lower().endswith(ext) for ext in self.media_extensions):
                return word

        return None

    @nextcord.slash_command(name="starboard", description="Configure the starboard system")
    @commands.has_permissions(manage_channels=True)
    async def starboard(self, interaction: nextcord.Interaction):
        pass

    @starboard.subcommand(name="setup", description="Set up the starboard channel")
    async def starboard_setup(
        self,
        interaction: nextcord.Interaction,
        channel: nextcord.TextChannel,
        threshold: Optional[int] = 3,
        allow_self_stars: Optional[bool] = False
    ):
        """Set up the starboard configuration for the server."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO starboard_config
            (guild_id, channel_id, star_threshold, self_star_allowed)
            VALUES (?, ?, ?, ?)
        ''', (interaction.guild.id, channel.id, threshold, allow_self_stars))
        self.conn.commit()

        embed = nextcord.Embed(
            title="Starboard Configuration",
            description=f"✨ Starboard has been set up!",
            color=nextcord.Color.gold()
        )
        embed.add_field(name="Starboard Channel", value=channel.mention, inline=False)
        embed.add_field(name="Star Threshold", value=threshold, inline=True)
        embed.add_field(name="Self Stars Allowed", value="Yes" if allow_self_stars else "No", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @starboard.subcommand(name="config", description="View current starboard configuration")
    async def starboard_config(self, interaction: nextcord.Interaction):
        """Display the current starboard configuration."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM starboard_config WHERE guild_id = ?', (interaction.guild.id,))
        config = cursor.fetchone()

        if not config:
            await interaction.response.send_message(
                "❌ No starboard configuration found. Use `/starboard setup` to configure.",
                ephemeral=True
            )
            return

        guild_id, channel_id, threshold, self_star_allowed = config
        channel = interaction.guild.get_channel(channel_id)

        embed = nextcord.Embed(
            title="Starboard Configuration",
            color=nextcord.Color.blue()
        )
        embed.add_field(name="Starboard Channel", value=channel.mention if channel else "Channel Deleted", inline=False)
        embed.add_field(name="Star Threshold", value=threshold, inline=True)
        embed.add_field(name="Self Stars Allowed", value="Yes" if self_star_allowed else "No", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: nextcord.Reaction, user: nextcord.Member):
        """Handle star reactions and manage starboard messages."""
        # Skip if the reaction is not a star
        if str(reaction.emoji) != "⭐":
            return

        # Fetch starboard configuration
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM starboard_config WHERE guild_id = ?', (reaction.message.guild.id,))
        config = cursor.fetchone()

        if not config:
            return  # No starboard setup for this guild

        channel_id, threshold, self_star_allowed = config[1], config[2], config[3]
        starboard_channel = reaction.message.guild.get_channel(channel_id)

        # Check if user is trying to star their own message
        if not self_star_allowed and user.id == reaction.message.author.id:
            return

        # Check star count
        if reaction.count >= threshold:
            # Check if message is already in starboard
            cursor.execute('SELECT * FROM starred_messages WHERE message_id = ?', (reaction.message.id,))
            existing_star = cursor.fetchone()

            # Extract media URL
            media_url = self.extract_media_url(reaction.message)

            # Create starboard embed
            embed = nextcord.Embed(
                description=reaction.message.content or "No text content",
                color=nextcord.Color.gold(),
                timestamp=reaction.message.created_at
            )
            embed.set_author(
                name=f"{reaction.message.author.display_name} - ( {reaction.message.author.name} )",
                icon_url=reaction.message.author.display_avatar.url
            )
            embed.add_field(name="Original Message", value=f"[Jump to Message]({reaction.message.jump_url})")

            # Add media to embed if exists
            if media_url:
                # Check if URL is an image or video
                lower_url = media_url.lower()
                if any(lower_url.endswith(ext) for ext in ['.gif', '.png', '.jpg', '.jpeg', '.webp']):
                    embed.set_image(url=media_url)
                else:
                    embed.set_image(media_url)

            if existing_star:
                # Update existing starboard message
                try:
                    starboard_msg = await starboard_channel.fetch_message(existing_star[3])
                    await starboard_msg.edit(
                        content=f"⭐ {reaction.count} | {reaction.message.channel.mention}",
                        embed=embed
                    )

                    cursor.execute('''
                        UPDATE starred_messages
                        SET star_count = ?, media_url = ?
                        WHERE message_id = ?
                    ''', (reaction.count, media_url, reaction.message.id))
                except nextcord.NotFound:
                    # Starboard message was deleted, recreate
                    starboard_msg = await starboard_channel.send(
                        content=f"⭐ {reaction.count} | {reaction.message.channel.mention}",
                        embed=embed
                    )

                    cursor.execute('''
                        UPDATE starred_messages
                        SET starboard_message_id = ?, star_count = ?, media_url = ?
                        WHERE message_id = ?
                    ''', (starboard_msg.id, reaction.count, media_url, reaction.message.id))
            else:
                # Create new starboard message
                starboard_msg = await starboard_channel.send(
                    content=f"⭐ {reaction.count} | {reaction.message.channel.mention}",
                    embed=embed
                )

                # Store in database
                cursor.execute('''
                    INSERT INTO starred_messages
                    (message_id, guild_id, original_channel_id, starboard_message_id, star_count, original_author_id, media_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    reaction.message.id,
                    reaction.message.guild.id,
                    reaction.message.channel.id,
                    starboard_msg.id,
                    reaction.count,
                    reaction.message.author.id,
                    media_url
                ))

            self.conn.commit()

    def cog_unload(self):
        """Close database connection when cog is unloaded."""
        self.conn.close()

def setup(bot):
    bot.add_cog(StarboardCog(bot))