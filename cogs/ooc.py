import random
import nextcord
from nextcord.ext import commands
from nextcord import Interaction
from datetime import datetime

class RandomUserCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_random_message(self):
        """Helper method to find a random message across guilds"""
        guilds = self.bot.guilds
        max_attempts = 10
        attempts = 0

        while attempts < max_attempts:
            attempts += 1

            random_guild = random.choice(guilds)
            text_channels = [ch for ch in random_guild.channels if isinstance(ch, nextcord.TextChannel)]

            if not text_channels:
                continue

            random_channel = random.choice(text_channels)

            try:
                messages = await random_channel.history(limit=100).flatten()

                random_message = random.choice(messages)

                if (not random_message.content or
                    random_message.author.bot or
                    len(random_message.content) < 3):
                    continue

                return random_message

            except nextcord.Forbidden:
                continue

        return None

    @commands.command(name="out_of_context", aliases=["ooc"])
    async def traditional_ooc(self, ctx):
        """Traditional command version of out of context"""
        random_message = await self.fetch_random_message()

        if not random_message:
            await ctx.send("Could not find a random message. Try again!")
            return

        user = random_message.author

        # Format the timestamp to be more readable
        timestamp = random_message.created_at.strftime("%B %d, %Y at %I:%M %p")

        embed = nextcord.Embed(
            description=random_message.content,
            color=nextcord.Color.blue()
        )

        if user.avatar:
            embed.set_author(name=user.name, icon_url=user.avatar.url)
        else:
            embed.set_author(name=user.name)

        embed.set_footer(text=f"Sent on {timestamp} in #{random_message.channel.name} of {random_message.guild.name}")

        await ctx.send(embed=embed)

    @nextcord.slash_command(name="ooc", description="Get a random out-of-context message")
    async def slash_ooc(self, interaction: Interaction):
        """Slash command version of out of context"""
        await interaction.response.defer()

        random_message = await self.fetch_random_message()

        if not random_message:
            await interaction.followup.send("Could not find a random message. Try again!")
            return

        user = random_message.author

        # Format the timestamp to be more readable
        timestamp = random_message.created_at.strftime("%B %d, %Y at %I:%M %p")

        embed = nextcord.Embed(
            description=random_message.content,
            color=nextcord.Color.blue()
        )

        if user.avatar:
            embed.set_author(name=user.name, icon_url=user.avatar.url)
        else:
            embed.set_author(name=user.name)

        embed.set_footer(text=f"Sent on {timestamp} in #{random_message.channel.name} of {random_message.guild.name}")

        await interaction.followup.send(embed=embed)

def setup(bot):
    bot.add_cog(RandomUserCog(bot))