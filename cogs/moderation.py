import nextcord
from nextcord.ext import commands
from nextcord import SlashOption, Attachment
import sqlite3
from typing import Optional
from datetime import datetime, timedelta
from pytimeparse.timeparse import timeparse
import asyncio

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/moderation.db"
        self.create_tables()
        
    def get_connection(self):
        """Get a new database connection."""
        return sqlite3.connect(self.db_path)

    def create_tables(self):
        """Create necessary tables for moderation."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
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
            conn.commit()
        except sqlite3.Error as e:
            self.bot.logger.error(f"Database error: {e}")
        finally:
            conn.close()

    def get_next_case_id(self, guild_id):
        """Get the next unique case ID for a specific guild."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(MAX(case_id), 0) + 1 FROM cases WHERE guild_id = ?", (guild_id,))
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def get_log_channel(self, guild_id):
        """Fetch the mod log channel for a guild."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT log_channel_id FROM mod_log WHERE guild_id = ?", (guild_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            conn.close()

    async def log_action(self, guild, action, user, moderator, reason=None, duration=None, file=None, case_id=None):
        """Log moderation actions to the designated channel."""
        log_channel_id = self.get_log_channel(guild.id)
        if not log_channel_id:
            return
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return

        # Default color based on action severity
        color_map = {
            "Warn": nextcord.Color.yellow(),
            "Kick": nextcord.Color.orange(),
            "Timeout": nextcord.Color.blue(),
            "Temporary Ban": nextcord.Color.red(),
            "Permanent Ban": nextcord.Color.dark_red(),
        }
        color = color_map.get(action, nextcord.Color.red())

        embed = nextcord.Embed(title="", color=color)
        # Handle case where user has no avatar
        icon_url = user.avatar.url if user.avatar else None
        embed.set_author(name=f"#{case_id or 'N/A'} | {user.display_name} | {action}", icon_url=icon_url)
        embed.add_field(name="Target", value=f"{user.mention} ({user.name}: {user.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator.name}: {moderator.id})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        if duration:
            embed.add_field(name="Duration", value=str(duration), inline=False)
        embed.timestamp = datetime.now()
        
        try:
            if file:
                embed2 = nextcord.Embed(title="", description="Proof From Moderator", color=color)
                embed2.set_image(url=file.url)
                await log_channel.send(embeds=[embed, embed2])
            else:
                await log_channel.send(embed=embed)
        except nextcord.Forbidden:
            pass
        except Exception as e:
            print(f"Error logging moderation action: {e}")

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
            # Silently pass if user has DMs disabled
            pass
        except Exception as e:
            print(f"Error sending DM to user: {e}")

    @nextcord.slash_command(name="modlog", description="Set the moderation log channel.")
    @commands.has_permissions(administrator=True)
    async def set_mod_log(
        self,
        interaction: nextcord.Interaction,
        channel: nextcord.TextChannel = SlashOption(description="The channel to set as mod log")
    ):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO mod_log (guild_id, log_channel_id) VALUES (?, ?)",
                (interaction.guild.id, channel.id)
            )
            conn.commit()

            embed = nextcord.Embed(
                title="Moderation Log Channel Set",
                description=f"The mod log channel has been set to {channel.mention}.",
                color=nextcord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except sqlite3.Error as e:
            embed = nextcord.Embed(
                title="Error",
                description=f"Failed to set moderation log channel: {str(e)}",
                color=nextcord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            conn.close()

    @nextcord.slash_command(name="warn", description="Warn a user.")
    @commands.has_permissions(moderate_members=True)
    async def warn(
        self,
        interaction: nextcord.Interaction,
        user: nextcord.Member = SlashOption(description="The user to warn"),
        reason: str = SlashOption(description="The reason for the warning"),
        proof: Optional[Attachment] = SlashOption(description="Picture or something", required=False)
    ):
        if user.id == interaction.user.id:
            await interaction.response.send_message("You cannot warn yourself.", ephemeral=True)
            return
            
        if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("You cannot warn users with a higher or equal role than yours.", ephemeral=True)
            return
            
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            case_id = self.get_next_case_id(interaction.guild.id)

            cursor.execute(
                "INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                (user.id, interaction.guild.id, interaction.user.id, reason, datetime.now().isoformat())
            )

            cursor.execute(
                "INSERT INTO cases (case_id, user_id, guild_id, moderator_id, action, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (case_id, user.id, interaction.guild.id, interaction.user.id, "warn", reason, datetime.now().isoformat())
            )

            conn.commit()

            embed = nextcord.Embed(
                title="User Warned",
                description=f"{user.mention} has been warned.",
                color=nextcord.Color.yellow()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Case ID", value=str(case_id), inline=False)
            await interaction.response.send_message(embed=embed)

            await self.log_action(interaction.guild, "Warn", user, interaction.user, reason, file=proof, case_id=case_id)
            await self.send_dm(user, "Warn", reason, file=proof, case_id=case_id)
        except sqlite3.Error as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        finally:
            conn.close()

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
        if user.id == interaction.user.id:
            await interaction.response.send_message("You cannot ban yourself.", ephemeral=True)
            return
            
        if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("You cannot ban users with a higher or equal role than yours.", ephemeral=True)
            return
            
        parsed_duration = timeparse(duration) if duration else None
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            case_id = self.get_next_case_id(interaction.guild.id)

            # First send DM to user before banning
            await self.send_dm(
                user, 
                "Temporary Ban" if parsed_duration else "Permanent Ban", 
                reason, 
                duration if parsed_duration else "Permanent", 
                file=proof, 
                case_id=case_id
            )

            if parsed_duration:
                # Temporary ban
                try:
                    await user.ban(reason=reason)
                    cursor.execute("""
                        INSERT INTO cases (case_id, user_id, guild_id, moderator_id, action, reason, duration, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (case_id, user.id, interaction.guild.id, interaction.user.id, "temporary ban", reason, duration, datetime.now().isoformat()))
                    conn.commit()

                    embed = nextcord.Embed(
                        title="User Temporarily Banned",
                        description=f"{user.mention} has been banned for {duration}.",
                        color=nextcord.Color.red()
                    )
                    embed.add_field(name="Reason", value=reason, inline=False)
                    embed.add_field(name="Case ID", value=str(case_id), inline=False)
                    await interaction.response.send_message(embed=embed)

                    await self.log_action(interaction.guild, "Temporary Ban", user, interaction.user, reason, duration, file=proof, case_id=case_id)
                    
                    # Schedule unban asynchronously
                    # This is better than using sleep_until as it won't block the bot
                    self.bot.loop.create_task(self.schedule_unban(interaction.guild, user, parsed_duration, case_id))
                    
                except nextcord.Forbidden:
                    await interaction.response.send_message("I don't have permission to ban this user.", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"Failed to ban user: {str(e)}", ephemeral=True)
            else:
                # Permanent ban
                try:
                    await user.ban(reason=reason)
                    cursor.execute("""
                        INSERT INTO cases (case_id, user_id, guild_id, moderator_id, action, reason, duration, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (case_id, user.id, interaction.guild.id, interaction.user.id, "permanent ban", reason, "Permanent", datetime.now().isoformat()))
                    conn.commit()

                    embed = nextcord.Embed(
                        title="User Permanently Banned",
                        description=f"{user.mention} has been permanently banned.",
                        color=nextcord.Color.red()
                    )
                    embed.add_field(name="Reason", value=reason, inline=False)
                    embed.add_field(name="Case ID", value=str(case_id), inline=False)
                    await interaction.response.send_message(embed=embed)

                    await self.log_action(interaction.guild, "Permanent Ban", user, interaction.user, reason, "Permanent", file=proof, case_id=case_id)
                    
                except nextcord.Forbidden:
                    await interaction.response.send_message("I don't have permission to ban this user.", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"Failed to ban user: {str(e)}", ephemeral=True)
        except sqlite3.Error as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        finally:
            conn.close()
            
    async def schedule_unban(self, guild, user, duration_seconds, case_id):
        """Handle scheduled unbans without blocking the bot."""
        try:
            await asyncio.sleep(duration_seconds)
            
            # Check if the ban still exists before removing
            bans = [ban.user.id for ban in await guild.bans()]
            if user.id in bans:
                await guild.unban(user, reason=f"Temporary ban expired (Case #{case_id})")
                
                # Log the unban action
                mod_bot = nextcord.Object(id=self.bot.user.id)
                await self.log_action(
                    guild, 
                    "Unban", 
                    user, 
                    self.bot.user, 
                    reason=f"Temporary ban expired (Case #{case_id})"
                )
        except Exception as e:
            print(f"Error in scheduled unban: {e}")

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
        if user.id == interaction.user.id:
            await interaction.response.send_message("You cannot timeout yourself.", ephemeral=True)
            return
            
        if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("You cannot timeout users with a higher or equal role than yours.", ephemeral=True)
            return
            
        parsed_duration = timeparse(duration)
        
        if not parsed_duration:
            embed = nextcord.Embed(
                title="Invalid Duration",
                description="Please provide a valid duration string (e.g., '1h30m').",
                color=nextcord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        # Discord has a max timeout of 28 days
        if parsed_duration > 28 * 24 * 60 * 60:  # 28 days in seconds
            embed = nextcord.Embed(
                title="Invalid Duration",
                description="The maximum timeout duration is 28 days.",
                color=nextcord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            case_id = self.get_next_case_id(interaction.guild.id)

            try:
                until = datetime.now() + timedelta(seconds=parsed_duration)
                await user.edit(timeout=nextcord.utils.utcnow()+timedelta(seconds=parsed_duration), reason=reason)
                
                cursor.execute("""
                    INSERT INTO cases (case_id, user_id, guild_id, moderator_id, action, reason, duration, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (case_id, user.id, interaction.guild.id, interaction.user.id, "timeout", reason, duration, datetime.now().isoformat()))
                conn.commit()

                embed = nextcord.Embed(
                    title="User Timed Out",
                    description=f"{user.mention} has been timed out for {duration}.",
                    color=nextcord.Color.blue()
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Case ID", value=str(case_id), inline=False)
                await interaction.response.send_message(embed=embed)

                await self.log_action(interaction.guild, "Timeout", user, interaction.user, reason, duration, file=proof, case_id=case_id)
                await self.send_dm(user, "Timeout", reason, duration, file=proof, case_id=case_id)
            except nextcord.Forbidden:
                await interaction.response.send_message("I don't have permission to timeout this user.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"Failed to timeout user: {str(e)}", ephemeral=True)
        except sqlite3.Error as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        finally:
            conn.close()

    @nextcord.slash_command(name="kick", description="Kick a user.")
    @commands.has_permissions(kick_members=True)
    async def kick(
        self,
        interaction: nextcord.Interaction,
        user: nextcord.Member = SlashOption(description="The user to kick"),
        reason: str = SlashOption(description="The reason for the kick", required=False, default="No reason provided"),
        proof: Optional[Attachment] = SlashOption(description="Picture or something", required=False)
    ):
        if user.id == interaction.user.id:
            await interaction.response.send_message("You cannot kick yourself.", ephemeral=True)
            return
            
        if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("You cannot kick users with a higher or equal role than yours.", ephemeral=True)
            return

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            case_id = self.get_next_case_id(interaction.guild.id)

            # Send DM first before kicking
            await self.send_dm(user, "Kick", reason, file=proof, case_id=case_id)
            
            try:
                cursor.execute("""
                    INSERT INTO cases (case_id, user_id, guild_id, moderator_id, action, reason, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (case_id, user.id, interaction.guild.id, interaction.user.id, "kick", reason, datetime.now().isoformat()))
                conn.commit()

                await user.kick(reason=reason)
                embed = nextcord.Embed(
                    title="User Kicked",
                    description=f"{user.mention} has been kicked.",
                    color=nextcord.Color.orange()
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Case ID", value=str(case_id), inline=False)
                await interaction.response.send_message(embed=embed)

                await self.log_action(interaction.guild, "Kick", user, interaction.user, reason, file=proof, case_id=case_id)
            except nextcord.Forbidden:
                await interaction.response.send_message("I don't have permission to kick this user.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"Failed to kick user: {str(e)}", ephemeral=True)
        except sqlite3.Error as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        finally:
            conn.close()
            
    @nextcord.slash_command(name="case", description="Look up case information.")
    @commands.has_permissions(moderate_members=True)
    async def case_lookup(
        self,
        interaction: nextcord.Interaction,
        case_id: int = SlashOption(description="The case ID to look up")
    ):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, moderator_id, action, reason, duration, timestamp 
                FROM cases 
                WHERE guild_id = ? AND case_id = ?
            """, (interaction.guild.id, case_id))
            
            result = cursor.fetchone()
            if not result:
                await interaction.response.send_message(f"Case #{case_id} not found.", ephemeral=True)
                return
                
            user_id, moderator_id, action, reason, duration, timestamp = result
            
            # Try to get user and moderator objects
            user = interaction.guild.get_member(user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                except:
                    user = f"Unknown User (ID: {user_id})"
            
            moderator = interaction.guild.get_member(moderator_id)
            if not moderator:
                try:
                    moderator = await self.bot.fetch_user(moderator_id)
                except:
                    moderator = f"Unknown Moderator (ID: {moderator_id})"
                
            # Create embed
            embed = nextcord.Embed(title=f"Case #{case_id}", color=nextcord.Color.blue())
            
            # Format user info
            if isinstance(user, (nextcord.Member, nextcord.User)):
                user_info = f"{user.mention} ({user.name}: {user.id})"
            else:
                user_info = str(user)
                
            # Format moderator info
            if isinstance(moderator, (nextcord.Member, nextcord.User)):
                mod_info = f"{moderator.mention} ({moderator.name}: {moderator.id})"
            else:
                mod_info = str(moderator)
            
            # Add fields
            embed.add_field(name="User", value=user_info, inline=False)
            embed.add_field(name="Action", value=action.title(), inline=True)
            embed.add_field(name="Moderator", value=mod_info, inline=False)
            embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
            
            if duration:
                embed.add_field(name="Duration", value=duration, inline=True)
                
            # Format timestamp
            try:
                case_time = datetime.fromisoformat(timestamp)
                embed.timestamp = case_time
                embed.set_footer(text="Case created")
            except:
                embed.add_field(name="Timestamp", value=timestamp, inline=False)
                
            await interaction.response.send_message(embed=embed)
            
        except sqlite3.Error as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        finally:
            conn.close()

    def cog_unload(self):
        """Close the database connection when the cog is unloaded."""
        # No need to close a connection here as we're using per-method connections now
        pass

def setup(bot):
    bot.add_cog(Moderation(bot))
