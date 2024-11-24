import nextcord
from nextcord.ext import commands
from nextcord import slash_command
from nextcord import Interaction as interaction

class Mayo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="mayo")
    async def example(self, interaction):
        await interaction.reply('https://media.tenor.com/6mHLDBj4i6MAAAAM/mayo-mayonnaise.gif')

def setup(bot):
    bot.add_cog(Mayo(bot))
