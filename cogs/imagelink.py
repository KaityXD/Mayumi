import nextcord
from nextcord.ext import commands
from nextcord import Interaction, Attachment
from typing import Optional

class ImageLinkCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @nextcord.slash_command(name="imagelink", description="Get a link to an uploaded image")
    async def image_link(
        self, 
        interaction: Interaction, 
        image: Optional[Attachment] = None
    ):
        if not image:
            await interaction.response.send_message("Please upload an image.", ephemeral=True)
            return

        if not image.content_type:
            await interaction.response.send_message("Please upload a valid image file.", ephemeral=True)
            return

        await interaction.response.send_message(image.url)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(ImageLinkCog(bot))
