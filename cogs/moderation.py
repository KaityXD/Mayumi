import nextcord
from nextcord.ext import commands
from nextcord import SlashOption, Attachment
import sqlite3
from typing import Optional
from datetime import datetime, timedelta
from pytimeparse.timeparse import timeparse

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("db/moderation.db")
        self.create_tables()

    def create_tables(self):
        """Create necessary tables for moderation."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mod_log (
                guild_id INTEGER,
                log_channel_id INTEGER,
                PRIMARY KEY (guild_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                timestamp TEXT,
                UNIQUE(guild_id, warning_id)
            )
        """)
        cursor.execute("""
           CREATE TABLE IF NOT EXISTS cases (
               case_id INTEGER,
               guild_id INTEGER,
               user_id INTEGER,
               moderator_id INTEGER,
               action TEXT,
               reason TEXT,
               duration TEXT,
               timestamp TEXT,
               PRIMARY KEY (guild_id, case_id)
           )
        """)
        self.conn.commit()

    def get_next_case_id(self, guild_id):
        """Get the next unique case ID for a specific guild."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(case_id), 0) + 1 FROM cases WHERE guild_id = ?", (guild_id,))
        return cursor.fetchone()[0]

    def get_log_channel(self, guild_id):
        """Fetch the mod log channel for a guild."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT log_channel_id FROM mod_log WHERE guild_id = ?", (guild_id,))
        result = cursor.fetchone()
        return result[0] if result else None

    async def log_action(self, guild, action, user, moderator, reason=None, duration=None, file=None, case_id=None):
        """Log moderation actions to the designated channel."""
        log_channel_id = self.get_log_channel(guild.id)
        if not log_channel_id:
            return
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return

        embed = nextcord.Embed(title="", color=nextcord.Color.red())
        embed.set_author(name=f"#{case_id or 'N/A'} | {user.display_name} | {action}", icon_url=user.avatar.url)
        embed.add_field(name="Target", value=f"{user.mention} ({user.name}: {user.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator.name}: {moderator.id})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        if duration:
            embed.add_field(name="Duration", value=str(duration), inline=False)
        embed.timestamp = datetime.now()
        if file:
            embed2 = nextcord.Embed(title="", description="Proof From Moderator", color=nextcord.Color.red())
            embed2.set_image(url=file.url)
            await log_channel.send(embeds=[embed, embed2])
        else:
            await log_channel.send(embed=embed)

    async def send_dm(self, user, action, reason=None, duration=None, file=None, case_id=None):
        """Send a direct message to the moderated user."""
        try:
            embed = nextcord.Embed(title="You Have Been Moderated", color=nextcord.Color.orange())
            if case_id:
                embed.set_footer(text=f"Case ID: {case_id}")
            embed.add_field(name="Action", value=action, inline=False)
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            if duration:
                embed.add_field(name="Duration", value=str(duration), inline=False)

            embed.timestamp = datetime.now()
            if file:
                embed2 = nextcord.Embed(
                    title="",
                    description="Proof From Moderator",
                    color=nextcord.Color.red()
                )
                embed2.set_image(url=file.url)
                await user.send(embeds=[embed, embed2])
            else:
                await user.send(embed=embed)
        except nextcord.Forbidden:
            pass

    @nextcord.slash_command(name="modlog", description="Set the moderation log channel.")
    @commands.has_permissions(administrator=True)
    async def set_mod_log(
        self,
        interaction: nextcord.Interaction,
        channel: nextcord.TextChannel = SlashOption(description="The channel to set as mod log")
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO mod_log (guild_id, log_channel_id) VALUES (?, ?)",
            (interaction.guild.id, channel.id)
        )
        self.conn.commit()

        embed = nextcord.Embed(
            title="Moderation Log Channel Set",
            description=f"The mod log channel has been set to {channel.mention}.",
            color=nextcord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @nextcord.slash_command(name="warn", description="Warn a user.")
    @commands.has_permissions(moderate_members=True)
    async def warn(
        self,
        interaction: nextcord.Interaction,
        user: nextcord.Member = SlashOption(description="The user to warn"),
        reason: str = SlashOption(description="The reason for the warning"),
        proof: Optional[Attachment] = SlashOption(description="Picture or something", required=False)
    ):
        cursor = self.conn.cursor()
        case_id = self.get_next_case_id(interaction.guild.id)

        cursor.execute(
            "INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user.id, interaction.guild.id, interaction.user.id, reason, datetime.now().isoformat())
        )

        cursor.execute(
            "INSERT INTO cases (case_id, user_id, guild_id, moderator_id, action, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (case_id, user.id, interaction.guild.id, interaction.user.id, "warn", reason, datetime.now().isoformat())
        )

        self.conn.commit()

        embed = nextcord.Embed(
            title="User Warned",
            description=f"{user.mention} has been warned.",
            color=nextcord.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

        await self.log_action(interaction.guild, "Warn", user, interaction.user, reason, file=proof, case_id=case_id)
        await self.send_dm(user, "Warn", reason, file=proof, case_id=case_id)

    @nextcord.slash_command(name="ban", description="Ban a user.")
    @commands.has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: nextcord.Interaction,
        user: nextcord.Member = SlashOption(description="The user to ban"),
        reason: str = SlashOption(description="The reason for the ban", required=False, default="No reason provided"),
        duration: str = SlashOption(description="Duration of the ban (e.g., '1h30m') for temporary bans. Leave blank for permanent.", required=False, default=None),
        proof: Optional[Attachment] = SlashOption(description="Picture or something", required=False)
    ):
        cursor = self.conn.cursor()
        parsed_duration = timeparse(duration) if duration else None
        case_id = self.get_next_case_id(interaction.guild.id)

        if parsed_duration:
            # Temporary ban
            until = datetime.now() + timedelta(seconds=parsed_duration)
            await user.ban(reason=reason)

            cursor.execute("""
                INSERT INTO cases (case_id, user_id, guild_id, moderator_id, action, reason, duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (case_id, user.id, interaction.guild.id, interaction.user.id, "temporary ban", reason, duration, datetime.now().isoformat()))
            self.conn.commit()

            embed = nextcord.Embed(
                title="User Temporarily Banned",
                description=f"{user.mention} has been banned for {duration}.",
                color=nextcord.Color.red()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)

            await self.log_action(interaction.guild, "Temporary Ban", user, interaction.user, reason, duration, file=proof, case_id=case_id)
            await self.send_dm(user, "Temporary Ban", reason, duration, file=proof, case_id=case_id)

            # Unban after the duration
            await nextcord.utils.sleep_until(until)
            await interaction.guild.unban(user, reason=f"Temporary ban of {duration} expired")
        else:
            # Permanent ban
            await user.ban(reason=reason)

            cursor.execute("""
                INSERT INTO cases (case_id, user_id, guild_id, moderator_id, action, reason, duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (case_id, user.id, interaction.guild.id, interaction.user.id, "permanent ban", reason, "Permanent", datetime.now().isoformat()))
            self.conn.commit()

            embed = nextcord.Embed(
                title="User Permanently Banned",
                description=f"{user.mention} has been permanently banned.",
                color=nextcord.Color.red()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)

            await self.log_action(interaction.guild, "Permanent Ban", user, interaction.user, reason, "Permanent", file=proof, case_id=case_id)
            await self.send_dm(user, "Permanent Ban", reason, file=proof, case_id=case_id)

    @nextcord.slash_command(name="timeout", description="Timeout a user.")
    @commands.has_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: nextcord.Interaction,
        user: nextcord.Member = SlashOption(description="The user to timeout"),
        duration: str = SlashOption(description="Duration of timeout (e.g., '1h30m')"),
        reason: str = SlashOption(description="The reason for the timeout", required=False, default="No reason provided"),
        proof: Optional[Attachment] = SlashOption(description="Picture or something", required=False)
    ):
        cursor = self.conn.cursor()
        parsed_duration = timeparse(duration)
        case_id = self.get_next_case_id(interaction.guild.id)

        if not parsed_duration:
            embed = nextcord.Embed(
                title="Invalid Duration",
                description="Please provide a valid duration string (e.g., '1h30m').",
                color=nextcord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        until = datetime.now() + timedelta(seconds=parsed_duration)
        await user.edit(timeout=nextcord.utils.utcnow()+timedelta(seconds=parsed_duration), reason=reason)

        cursor.execute("""
            INSERT INTO cases (case_id, user_id, guild_id, moderator_id, action, reason, duration, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (case_id, user.id, interaction.guild.id, interaction.user.id, "timeout", reason, duration, datetime.now().isoformat()))
        self.conn.commit()

        embed = nextcord.Embed(
            title="User Timed Out",
            description=f"{user.mention} has been timed out for {duration}.",
            color=nextcord.Color.blue()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

        await self.log_action(interaction.guild, "Timeout", user, interaction.user, reason, duration, file=proof, case_id=case_id)
        await self.send_dm(user, "Timeout", reason, duration, file=proof, case_id=case_id)

    @nextcord.slash_command(name="kick", description="Kick a user.")
    @commands.has_permissions(kick_members=True)
    async def kick(
        self,
        interaction: nextcord.Interaction,
        user: nextcord.Member = SlashOption(description="The user to kick"),
        reason: str = SlashOption(description="The reason for the kick", required=False, default="No reason provided"),
        proof: Optional[Attachment] = SlashOption(description="Picture or something", required=False)
    ):
        cursor = self.conn.cursor()
        case_id = self.get_next_case_id(interaction.guild.id)

        cursor.execute("""
            INSERT INTO cases (case_id, user_id, guild_id, moderator_id, action, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (case_id, user.id, interaction.guild.id, interaction.user.id, "kick", reason, datetime.now().isoformat()))
        self.conn.commit()

        await user.kick(reason=reason)
        embed = nextcord.Embed(
            title="User Kicked",
            description=f"{user.mention} has been kicked.",
            color=nextcord.Color.orange()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

        await self.log_action(interaction.guild, "Kick", user, interaction.user, reason, file=proof, case_id=case_id)
        await self.send_dm(user, "Kick", reason, file=proof, case_id=case_id)

    def cog_unload(self):
        """Close the database connection when the cog is unloaded."""
        self.conn.close()

def setup(bot):
    bot.add_cog(Moderation(bot))