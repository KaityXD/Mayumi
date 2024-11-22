import nextcord
from nextcord.ext import commands
from utils.eco import EconomySystem
import random
from datetime import datetime

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.economy = EconomySystem(db_path="db/economy.db")
        
    def cog_unload(self):
        self.economy.close()
        

    @commands.command(name="balance", aliases=["bal"])
    async def balance(self, ctx, member: nextcord.Member = None):
        try:
            target = member or ctx.author
            
            balance = self.economy.get_balance(target.id)

            embed = nextcord.Embed(
                title=f"💰 {target.display_name}'s Balance",
                color=nextcord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Wallet", value=f"${balance['wallet']:,}", inline=False)
            embed.add_field(name="Bank", value=f"${balance['bank']:,}", inline=False)
            embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            embed.set_thumbnail(url=target.avatar.url)

            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ An error occurred while fetching the balance: {e}")

    @commands.command()
    async def daily(self, ctx):
        """Claim your daily reward"""
        try:
            result = self.economy.claim_daily(ctx.author.id)
            embed = nextcord.Embed(title="✨ Daily Reward", color=0x3498db)
            embed.add_field(name="Amount", value=f"${result['amount']:,}")
            embed.add_field(name="Streak", value=f"{result['streak']} days")
            if result['streak_bonus'] > 0:
                embed.add_field(name="Streak Bonus", value=f"${result['streak_bonus']:,}")
            await ctx.send(embed=embed)
        except ValueError as e:
            await ctx.send(f"❌ {str(e)}")

    @commands.command()
    async def deposit(self, ctx, amount: str):
        """Deposit money into your bank"""
        try:
            if amount.lower() == "all":
                balance = self.economy.get_balance(ctx.author.id)
                amount = balance["wallet"]
            else:
                amount = int(amount)
                
            if amount <= 0:
                return await ctx.send("❌ Amount must be positive!")
                
            new_balance = self.economy.deposit(ctx.author.id, amount)
            embed = nextcord.Embed(title="🏦 Deposit Successful", color=0x2ecc71)
            embed.add_field(name="Deposited", value=f"${amount:,}")
            embed.add_field(name="New Wallet", value=f"${new_balance['wallet']:,}")
            embed.add_field(name="New Bank", value=f"${new_balance['bank']:,}")
            await ctx.send(embed=embed)
        except ValueError as e:
            await ctx.send(f"❌ {str(e)}")

    @commands.command()
    async def withdraw(self, ctx, amount: str):
        """Withdraw money from your bank"""
        try:
            if amount.lower() == "all":
                balance = self.economy.get_balance(ctx.author.id)
                amount = balance["bank"]
            else:
                amount = int(amount)
                
            if amount <= 0:
                return await ctx.send("❌ Amount must be positive!")
                
            new_balance = self.economy.withdraw(ctx.author.id, amount)
            embed = nextcord.Embed(title="🏦 Withdrawal Successful", color=0x2ecc71)
            embed.add_field(name="Withdrawn", value=f"${amount:,}")
            embed.add_field(name="New Wallet", value=f"${new_balance['wallet']:,}")
            embed.add_field(name="New Bank", value=f"${new_balance['bank']:,}")
            await ctx.send(embed=embed)
        except ValueError as e:
            await ctx.send(f"❌ {str(e)}")

    @commands.command()
    async def shop(self, ctx):
        """View the shop items"""
        items = self.economy.get_shop_items()
        if not items:
            return await ctx.send("❌ No items available in the shop!")
            
        embed = nextcord.Embed(title="🛍️ Shop", color=0x9b59b6)
        for item in items:
            stock = "∞" if item["stock"] == -1 else item["stock"]
            desc = f"Price: ${item['price']:,}\nStock: {stock}"
            if item["description"]:
                desc += f"\n{item['description']}"
            embed.add_field(name=item["name"], value=desc, inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def buy(self, ctx, *, item_name: str):
        """Buy an item from the shop"""
        try:
            result = self.economy.buy_item(ctx.author.id, item_name)
            embed = nextcord.Embed(title="✅ Purchase Successful", color=0x2ecc71)
            embed.add_field(name="Item", value=result["item"])
            embed.add_field(name="Price", value=f"${result['price']:,}")
            
            # Handle role rewards if any
            if result["role_reward"]:
                role = nextcord.utils.get(ctx.guild.roles, name=result["role_reward"])
                if role:
                    await ctx.author.add_roles(role)
                    embed.add_field(name="Role Reward", value=role.name, inline=False)
                    
            await ctx.send(embed=embed)
        except ValueError as e:
            await ctx.send(f"❌ {str(e)}")

    @commands.command()
    async def inventory(self, ctx):
        """View your inventory"""
        inventory = self.economy.get_inventory(ctx.author.id)
        if not inventory:
            return await ctx.send("Your inventory is empty!")
            
        embed = nextcord.Embed(title="🎒 Inventory", color=0xe74c3c)
        for item, quantity in inventory.items():
            embed.add_field(name=item, value=f"Quantity: {quantity}")
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Economy(bot))
