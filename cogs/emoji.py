import nextcord
from nextcord.ext import commands
import datetime
from typing import Dict, List
from collections import defaultdict

class EmojiLeaderboardView(nextcord.ui.View):
    def __init__(self, emoji_data: List[tuple], per_page: int = 10):
        super().__init__(timeout=60)
        self.current_page = 0
        self.emoji_data = emoji_data
        self.per_page = per_page
        self.max_pages = ((len(emoji_data) - 1) // per_page) + 1

    @nextcord.ui.button(emoji="⬅️", style=nextcord.ButtonStyle.blurple)
    async def previous_page(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    @nextcord.ui.button(emoji="➡️", style=nextcord.ButtonStyle.blurple)
    async def next_page(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            await self.update_message(interaction)

    def create_embed(self) -> nextcord.Embed:
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.emoji_data))
        
        embed = nextcord.Embed(
            title="🏆 Emoji Leaderboard",
            description="Top emoji contributors in the server",
            color=0x00ff00,
            timestamp=datetime.datetime.now()
        )

        for idx, (user_id, emoji_count, emoji_list) in enumerate(self.emoji_data[start_idx:end_idx], start=start_idx + 1):
            medal = ""
            if idx == 1:
                medal = "🥇"
            elif idx == 2:
                medal = "🥈"
            elif idx == 3:
                medal = "🥉"
            else:
                medal = "◼️"

            # Display some of the emojis they added (up to 5)
            emoji_preview = " ".join(str(emoji) for emoji in emoji_list[:5])
            if len(emoji_list) > 5:
                emoji_preview += " ..."

            embed.add_field(
                name=f"{medal} Rank #{idx}",
                value=f"<@{user_id}>\nEmojis Added: {emoji_count}\nRecent Additions: {emoji_preview}",
                inline=False
            )

        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages}")
        return embed

    async def update_message(self, interaction: nextcord.Interaction):
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

class EmojiLeaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_emoji_data(self, guild: nextcord.Guild) -> Dict[int, List[nextcord.Emoji]]:
        """Fetch emoji creation data from server audit logs"""
        emoji_data = defaultdict(list)
        
        try:
            # Fetch audit logs for emoji creation
            async for entry in guild.audit_logs(action=nextcord.AuditLogAction.emoji_create, limit=None):
                if entry.user:  # Make sure we have a valid user
                    # Store the actual emoji object
                    target_emoji = entry.target
                    if target_emoji and isinstance(target_emoji, nextcord.Emoji):
                        emoji_data[entry.user.id].append(target_emoji)
        except nextcord.Forbidden:
            return None
        
        return emoji_data

    @commands.command(name="emojileaderboard", aliases=["emojirank", "emojilb"])
    @commands.has_permissions(view_audit_log=True)
    async def show_leaderboard(self, ctx: commands.Context):
        """Shows the emoji creation leaderboard based on server audit logs"""
        async with ctx.typing():
            # Fetch emoji data from audit logs
            emoji_data = await self.fetch_emoji_data(ctx.guild)
            
            if emoji_data is None:
                await ctx.send("❌ I don't have permission to view audit logs!")
                return
                
            if not emoji_data:
                await ctx.send("No emoji creation data found in audit logs! 😢")
                return

            # Convert to list of tuples (user_id, emoji_count, emoji_list)
            sorted_data = sorted(
                [(user_id, len(emojis), emojis) for user_id, emojis in emoji_data.items()],
                key=lambda x: x[1],
                reverse=True
            )

            # Create and send the paginated view
            view = EmojiLeaderboardView(sorted_data)
            await ctx.send(embed=view.create_embed(), view=view)

    @show_leaderboard.error
    async def leaderboard_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need 'View Audit Log' permission to use this command!")

def setup(bot):
    bot.add_cog(EmojiLeaderboard(bot))
