import nextcord
from nextcord.ext import commands
import traceback
import sys
from typing import Any, Optional, Union

class SlashErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_application_command_error(self, interaction: nextcord.Interaction, error: Exception):
        """Handle errors that occur during slash command execution."""
        
        # If command is on cooldown
        if isinstance(error, commands.CommandOnCooldown):
            minutes, seconds = divmod(error.retry_after, 60)
            hours, minutes = divmod(minutes, 60)
            hours = hours % 24
            if hours == 0 and minutes == 0:
                await interaction.send(f"Please wait {int(seconds)} seconds to use this command again.", ephemeral=True)
            elif hours == 0:
                await interaction.send(f"Please wait {int(minutes)}m {int(seconds)}s to use this command again.", ephemeral=True)
            else:
                await interaction.send(f"Please wait {int(hours)}h {int(minutes)}m {int(seconds)}s to use this command again.", ephemeral=True)
            return

        # If user is missing required permissions
        elif isinstance(error, commands.MissingPermissions):
            missing_perms = ", ".join(error.missing_permissions)
            await interaction.send(f"You're missing the following permissions to use this command: `{missing_perms}`", ephemeral=True)
            return

        # If bot is missing required permissions
        elif isinstance(error, commands.BotMissingPermissions):
            missing_perms = ", ".join(error.missing_permissions)
            await interaction.send(f"I'm missing the following permissions to execute this command: `{missing_perms}`", ephemeral=True)
            return

        # If interaction is unknown/expired
        elif isinstance(error, nextcord.errors.NotFound):
            await interaction.send("This interaction has expired.", ephemeral=True)
            return

        # If interaction failed
        elif isinstance(error, nextcord.errors.ApplicationInvokeError):
            original_error = error.original
            if isinstance(original_error, nextcord.Forbidden):
                await interaction.send("I don't have permission to execute this command.", ephemeral=True)
                return

        # General error handling
        else:
            # Print the error to console for debugging
            print('Ignoring exception in command {}:'.format(interaction.application_command.name), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            
            try:
                await interaction.send(
                    "An unexpected error occurred while running this command. Please try again later.",
                    ephemeral=True
                )
            except nextcord.errors.NotFound:
                # If the interaction token has expired, we can't send a response
                pass

def setup(bot):
    bot.add_cog(SlashErrorHandler(bot))
