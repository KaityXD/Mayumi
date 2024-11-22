import nextcord
from nextcord.ext import commands
from nextcord.ui import Button, View
from typing import List, Dict, Optional
from utils.eco import EconomySystem
import humanize
from datetime import datetime

class LeaderboardView(View):
    def __init__(self, cog, ctx, total_pages, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.current_page = 1
        self.total_pages = total_pages
        self.create_buttons()

    def create_buttons(self):
        self.first_page = Button(emoji="⏮️", style=nextcord.ButtonStyle.secondary, disabled=True)
        self.prev_page = Button(emoji="◀️", style=nextcord.ButtonStyle.primary, disabled=True)
        self.next_page = Button(emoji="▶️", style=nextcord.ButtonStyle.primary, disabled=(self.total_pages == 1))
        self.last_page = Button(emoji="⏭️", style=nextcord.ButtonStyle.secondary, disabled=(self.total_pages == 1))

        self.first_page.callback = self.first_page_callback
        self.prev_page.callback = self.prev_page_callback
        self.next_page.callback = self.next_page_callback
        self.last_page.callback = self.last_page_callback

        self.add_item(self.first_page)
        self.add_item(self.prev_page)
        self.add_item(self.next_page)
        self.add_item(self.last_page)

    async def first_page_callback(self, interaction: nextcord.Interaction):
        await self.change_page(interaction, 1)

    async def prev_page_callback(self, interaction: nextcord.Interaction):
        await self.change_page(interaction, self.current_page - 1)

    async def next_page_callback(self, interaction: nextcord.Interaction):
        await self.change_page(interaction, self.current_page + 1)

    async def last_page_callback(self, interaction: nextcord.Interaction):
        await self.change_page(interaction, self.total_pages)

    async def change_page(self, interaction: nextcord.Interaction, page):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ You can't use this menu.", ephemeral=True)
            return

        self.current_page = page
        self.first_page.disabled = page == 1
        self.prev_page.disabled = page == 1
        self.next_page.disabled = page == self.total_pages
        self.last_page.disabled = page == self.total_pages

        embed = await self.cog.get_leaderboard_embed(page)
        await interaction.response.edit_message(embed=embed, view=self)

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.economy = EconomySystem(db_path="db/economy.db")

    def format_currency(self, amount: int) -> str:
        """Format currency with appropriate suffixes."""
        if abs(amount) >= 1_000_000_000:  # Billion
            return f"{amount/1_000_000_000:.1f}B"
        elif abs(amount) >= 1_000_000:  # Million
            return f"{amount/1_000_000:.1f}M"
        elif abs(amount) >= 1_000:  # Thousand
            return f"{amount/1_000:.1f}K"
        return str(amount)

    async def get_user_display(self, user_id: int) -> str:
        """Get user display name with fallback."""
        user = self.bot.get_user(user_id)
        if user:
            return str(user)
        return f"Unknown User ({user_id})"

    def get_rank_emoji(self, rank: int) -> str:
        """Get appropriate emoji for ranking."""
        if rank == 1:
            return "👑"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        return f"`{rank}.`"

    async def get_leaderboard_embed(self, page: int) -> nextcord.Embed:
        """Generate leaderboard embed with available statistics."""
        limit = 10
        offset = (page - 1) * limit
    
        # Get leaderboard data using the economy system, with proper LIMIT and OFFSET
        leaderboard_data = self.economy.get_leaderboard(limit=limit, offset=offset)  # Pass offset here
        displayed_data = leaderboard_data  # Since we're now only fetching the relevant data, no need to slice it

        embed = nextcord.Embed(
            title="🏆 Wealth Leaderboard",
            color=nextcord.Color.gold(),
            timestamp=datetime.utcnow()
        )
    
        if not displayed_data:
            embed.description = "No data available."
            return embed
    
        # Calculate total wealth
        total_wealth = sum(total for _, total in leaderboard_data)
    
        for rank, (user_id, balance) in enumerate(displayed_data, start=offset + 1):
            user_display = await self.get_user_display(user_id)
            rank_emoji = self.get_rank_emoji(rank)
    
            # Calculate wealth percentage
            wealth_percentage = (balance / total_wealth * 100) if total_wealth > 0 else 0
    
            # Get user's balances
            user_balance = self.economy.get_balance(user_id)
            wallet = user_balance['wallet']
            bank = user_balance['bank']
    
            field_value = (
                f"💰 Total: `{self.format_currency(balance)}`\n"
                f"💵 Wallet: `{self.format_currency(wallet)}`\n"
                f"🏦 Bank: `{self.format_currency(bank)}`\n"
                f"📊 Wealth Share: `{wealth_percentage:.1f}%`"
            )
    
            embed.add_field(
                name=f"{rank_emoji} {user_display}",
                value=field_value,
                inline=False
            )
    
        embed.set_footer(text=f"Page {page} • Total Wealth: {self.format_currency(total_wealth)}")
        return embed

    @commands.command(name="leaderboard", aliases=["lb", "rich", "top"])
    async def leaderboard(self, ctx: commands.Context, page: int = 1):
        """
        View the server's wealthiest members!
        
        Usage:
        !leaderboard [page]
        
        Aliases: lb, rich, top
        """
        if page < 1:
            await ctx.send("❌ Page number must be positive!")
            return

        # Calculate total pages
        total_users = len(self.economy.get_leaderboard(1000))  # Get reasonable max for count
        total_pages = max((total_users - 1) // 10 + 1, 1)

        if page > total_pages:
            await ctx.send(f"❌ Invalid page number! Total pages: {total_pages}")
            return

        embed = await self.get_leaderboard_embed(page)
        view = LeaderboardView(self, ctx, total_pages)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="rank", aliases=["wealth"])
    async def rank(self, ctx: commands.Context, member: Optional[nextcord.Member] = None):
        """
        Check your or another member's wealth ranking.
        
        Usage:
        !rank [member]
        
        Aliases: wealth
        """
        user_id = member.id if member else ctx.author.id
        balance = self.economy.get_balance(user_id)

        # Calculate total wealth
        total_wealth = balance['wallet'] + balance['bank']

        # Get user's rank
        leaderboard = self.economy.get_leaderboard(1000)  # Get reasonable max
        rank = next((idx + 1 for idx, (uid, _) in enumerate(leaderboard) if uid == user_id), None)

        embed = nextcord.Embed(
            title=f"💰 Wealth Statistics for {member or ctx.author}",
            color=nextcord.Color.green(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(
            name="Wallet Balance",
            value=f"```{self.format_currency(balance['wallet'])}```",
            inline=True
        )
        embed.add_field(
            name="Bank Balance",
            value=f"```{self.format_currency(balance['bank'])}```",
            inline=True
        )
        embed.add_field(
            name="Total Wealth",
            value=f"```{self.format_currency(total_wealth)}```",
            inline=True
        )

        if rank:
            embed.add_field(
                name="Rank",
                value=f"{self.get_rank_emoji(rank)} `#{rank}`",
                inline=False
            )

        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Leaderboard(bot))
