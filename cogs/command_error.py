from nextcord.ext import commands
import math

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            try:
                await ctx.message.add_reaction("❌")
            except Exception:
                pass
        elif isinstance(error, commands.CommandOnCooldown):
            retry_after = math.ceil(error.retry_after)
            hours, remainder = divmod(retry_after, 3600)
            minutes, seconds = divmod(remainder, 60)

            if hours > 0:
                time_left = f"{hours}h {minutes}m"
            elif minutes > 0:
                time_left = f"{minutes}m {seconds}s"
            else:
                time_left = f"{seconds}s"

            try:
                await ctx.send(
                    f"⏳ This command is on cooldown. Try again in {time_left}.",
                    delete_after=5,
                )
            except Exception:
                pass

def setup(bot):
    bot.add_cog(ErrorHandler(bot))

