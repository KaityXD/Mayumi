import nextcord
import sqlite3
from nextcord.ext import commands
from nextcord import slash_command, Embed, Color, Interaction
from nextcord.errors import Forbidden

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_name = "db/moderation.db"
        self.create_table()

    def create_table(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_ids (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY(guild_id)
            )
        ''')
        conn.commit()
        conn.close()

    def create_error_embed(self, message: str) -> Embed:
        return Embed(
            description=f"<:false:1310781364991430656> *{message}*",
            color=Color.red()
        )

    def create_success_embed(self, message: str, reason: str = None) -> Embed:
        embed = Embed(
            description=f"✅ {message}",
            color=Color.green()
        )
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        return embed

    async def check_permissions(
        self,
        interaction: nextcord.Interaction,
        required_permission: str
    ) -> bool:
        has_permission = getattr(
            interaction.user.guild_permissions,
            required_permission,
            False
        )

        if not has_permission:
            embed = self.create_error_embed(
                f"You don't have permission to {required_permission.replace('_', ' ')}!"
            )
            await interaction.response.send_message(embed=embed)
            return False
        return True

    async def send_log(self, guild_id: int, embed: Embed):
        """Send log messages to the saved channel."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT channel_id FROM channel_ids WHERE guild_id = ?', (guild_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            channel_id = result[0]
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except Exception as e:
                    print(f"Failed to send log message: {e}")

    @slash_command(
        name="ban",
        description="Ban a member with an optional reason"
    )
    async def ban_command(
        self,
        interaction: nextcord.Interaction,
        member: nextcord.Member,
        reason: str = None
    ):
        if member.id == interaction.user.id:
            embed = self.create_error_embed("You cannot ban yourself!")
            await interaction.response.send_message(embed=embed)
            return

        if not await self.check_permissions(interaction, "ban_members"):
            return

        try:
            await member.ban(reason=reason)

            embed = self.create_success_embed(
                f"**{member.display_name}** has been banned.",
                reason
            )
            await interaction.response.send_message(embed=embed)

            # Log the action
            log_embed = Embed(
                title="Member Banned",
                color=Color.red(),
                description=f"**Member:** {member.mention}\n**Moderator:** {interaction.user.mention}"
            )
            if reason:
                log_embed.add_field(name="Reason", value=reason, inline=False)
            await self.send_log(interaction.guild.id, log_embed)

        except Forbidden:
            embed = self.create_error_embed(
                "I do not have enough permissions to ban this member!"
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            embed = self.create_error_embed(f"An error occurred: {str(e)}")
            await interaction.response.send_message(embed=embed)

    @slash_command(
        name="kick",
        description="Kick a member with an optional reason"
    )
    async def kick_command(
        self,
        interaction: nextcord.Interaction,
        member: nextcord.Member,
        reason: str = None
    ):
        if member.id == interaction.user.id:
            embed = self.create_error_embed("You cannot kick yourself!")
            await interaction.response.send_message(embed=embed)
            return

        if not await self.check_permissions(interaction, "kick_members"):
            return

        try:
            await member.kick(reason=reason)

            embed = self.create_success_embed(
                f"**{member.display_name}** has been kicked.",
                reason
            )
            await interaction.response.send_message(embed=embed)

            # Log the action
            log_embed = Embed(
                title="Member Kicked",
                color=Color.orange(),
                description=f"**Member:** {member.mention}\n**Moderator:** {interaction.user.mention}"
            )
            if reason:
                log_embed.add_field(name="Reason", value=reason, inline=False)
            await self.send_log(interaction.guild.id, log_embed)

        except Forbidden:
            embed = self.create_error_embed(
                "I do not have enough permissions to kick this member!"
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            embed = self.create_error_embed(f"An error occurred: {str(e)}")
            await interaction.response.send_message(embed=embed)

    @nextcord.slash_command(
        name="set_channel",
        description="Set the channel where the moderation log should send to"
    )
    async def save_channel(
            self,
            interaction: Interaction ,
            channel: nextcord.TextChannel = None
    ):
        if channel:
            channel_id = channel.id
        else:
            channel_id = interaction.channel.id
        guild_id = interaction.guild.id

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO channel_ids (guild_id, channel_id)
            VALUES (?, ?)
        ''', (guild_id, channel_id))
        conn.commit()
        conn.close()

        await interaction.response.send_message("Moderation log channel has been set.")

def setup(bot):
    bot.add_cog(Moderation(bot))

