import nextcord
from nextcord.ext import commands
from nextcord import slash_command
from nextcord import Interaction as interaction

class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="shutdown", description="shut down the bot")
    async def example(self, interaction):
        if not interaction.user.name == "kaityez":
            await interaction.send("nuh uh bro what you trying to do")
        else:
            await interaction.send("shutting down")
            await exit()

def setup(bot):
    bot.add_cog(MyCog(bot))
