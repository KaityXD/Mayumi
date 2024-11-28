import nextcord
from nextcord.ext import commands
from utils.eco import EconomySystem

def parse_amount(amount_str: str) -> int:
    """Convert string amounts with k/m/b suffixes to integers"""
    amount_str = amount_str.lower().strip()
    multipliers = {
        'k': 1000,
        'm': 1000000,
        'b': 1000000000
    }
    
    try:
        if amount_str[-1] in multipliers:
            number = float(amount_str[:-1])
            return int(number * multipliers[amount_str[-1]])
        return int(float(amount_str))
    except (ValueError, IndexError):
        raise ValueError("Invalid amount format")

def format_amount(amount: int) -> str:
    """Format large numbers to k/m/b format"""
    if amount >= 1000000000:
        return f"{amount/1000000000:.1f}B"
    if amount >= 1000000:
        return f"{amount/1000000:.1f}M"
    if amount >= 1000:
        return f"{amount/1000:.1f}K"
    return str(amount)

class Payment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.economy = EconomySystem()

    @commands.command(name="pay")
    async def pay(self, ctx, recipient: nextcord.Member, amount: str):
        """
        Transfer money to another user
        Usage: !pay @user <amount>
        Examples: !pay @user 1000, !pay @user 1k, !pay @user 1.5m
        """
        try:
            # Parse the amount with k/m/b support
            parsed_amount = parse_amount(amount)
            
            # Check if amount is positive
            if parsed_amount <= 0:
                await ctx.reply("❌ Amount must be positive!")
                return

            # Get sender's balance
            sender_balance = self.economy.get_balance(ctx.author.id)

            # Validation checks
            if sender_balance["wallet"] < parsed_amount:
                await ctx.reply(f"❌ Insufficient funds! You need {format_amount(parsed_amount)} coins but only have {format_amount(sender_balance['wallet'])}!")
                return

            if ctx.author.id == recipient.id:
                await ctx.reply("❌ You can't pay yourself!")
                return

            # Process the payment
            self.economy.update_balance(
                ctx.author.id,
                -parsed_amount,
                "transfer_sent",
                f"Payment to {recipient.display_name}"
            )

            self.economy.update_balance(
                recipient.id,
                parsed_amount,
                "transfer_received",
                f"Payment from {ctx.author.display_name}"
            )

            # Get updated balances
            new_sender_balance = self.economy.get_balance(ctx.author.id)
            new_recipient_balance = self.economy.get_balance(recipient.id)

            # Create an improved embed
            embed = nextcord.Embed(
                title="Payment Successful",
                description=f"💸 **{format_amount(parsed_amount)}** coins transferred!",
                color=nextcord.Color.green()
            )
            
            # Sender info
            embed.add_field(
                name="👤 Sender",
                value=f"**User:** {ctx.author.mention}\n"
                      f"**Previous Balance:** {format_amount(sender_balance['wallet'])} 🪙\n"
                      f"**New Balance:** {format_amount(new_sender_balance['wallet'])} 🪙",
                inline=False
            )
            
            # Recipient info
            embed.add_field(
                name="📥 Recipient",
                value=f"**User:** {recipient.mention}\n"
                      f"**Previous Balance:** {format_amount(new_recipient_balance['wallet'] - parsed_amount)} 🪙\n"
                      f"**New Balance:** {format_amount(new_recipient_balance['wallet'])} 🪙",
                inline=False
            )

            # Add timestamp
            embed.timestamp = ctx.message.created_at
            embed.set_footer(text=f"Transaction ID: {ctx.message.id}")

            await ctx.reply(embed=embed)

        except ValueError as e:
            await ctx.reply(f"❌ Invalid amount format! Please use numbers with optional k/m/b suffix (e.g., 1000, 1k, 1.5m)")
        except Exception as e:
            await ctx.reply(f"❌ An error occurred: {str(e)}")

def setup(bot):
    bot.add_cog(Payment(bot))
