import os
from typing import Optional, List, Literal
from dataclasses import dataclass
from utils.config import OWNER_ID
import nextcord
from nextcord import Interaction, ButtonStyle, Embed, Color
from nextcord.ext import commands
from nextcord.ext.commands import Bot
from difflib import get_close_matches
from colorama import Fore, init

ActionType = Literal["load", "unload", "reload"]
init(autoreset=True)

@dataclass
class CogOperation:
    """Represents a cog operation with its status and error message if any."""
    success: bool
    message: str
    error: Optional[Exception] = None

class ConfirmView(nextcord.ui.View):
    """View for confirmation buttons when managing cogs."""
    
    def __init__(
        self, 
        interaction: Interaction, 
        bot: Bot, 
        action: ActionType, 
        cog_name: str,
        owner_id: int
    ):
        super().__init__(timeout=30)
        self.interaction = interaction
        self.bot = bot
        self.action = action
        self.cog_name = cog_name
        self.owner_id = owner_id

    async def handle_cog_operation(self) -> CogOperation:
        """Execute the requested cog operation and return the result."""
        try:
            cog_path = f"cogs.{self.cog_name}"
            if self.action == "load":
                self.bot.load_extension(cog_path)
            elif self.action == "unload":
                self.bot.unload_extension(cog_path)
            else:  # reload
                self.bot.reload_extension(cog_path)
                
            return CogOperation(
                success=True,
                message=f"{self.action.capitalize()}ed cog: `{self.cog_name}` successfully."
            )
        except Exception as e:
            return CogOperation(
                success=False,
                message=f"Failed to {self.action} cog `{self.cog_name}`",
                error=e
            )

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Check if the user has permission to use the buttons."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "You don't have permission to use this button.", 
                ephemeral=True
            )
            return False
        return True

    @nextcord.ui.button(label="Confirm", style=ButtonStyle.green)
    async def confirm(self, button: nextcord.ui.Button, interaction: Interaction):
        """Handle confirmation button press."""
        result = await self.handle_cog_operation()
        
        if result.error:
            error_details = f"\nError: {str(result.error)}" if result.error else ""
            await self.interaction.followup.send(f"{result.message}{error_details}")
        else:
            await self.interaction.followup.send(result.message)
        
        self.stop()

    @nextcord.ui.button(label="Cancel", style=ButtonStyle.red)
    async def cancel(self, button: nextcord.ui.Button, interaction: Interaction):
        """Handle cancellation button press."""
        await interaction.response.send_message("Action canceled.", ephemeral=True)
        self.stop()

class CogManager(commands.Cog):
    """A cog for managing other cogs through slash commands."""

    def __init__(self, bot: Bot, owner_id: int):
        self.bot = bot
        self.owner_id = owner_id
        self.cogs_directory = "cogs"

    async def cog_check(self, interaction: Interaction) -> bool:
        """Check if the user has permission to use cog management commands."""
        return interaction.user.id == self.owner_id

    def get_available_cogs(self) -> List[str]:
        """Get a list of all available cog files in the cogs directory."""
        if not os.path.exists(self.cogs_directory):
            return []
        
        return [
            f.replace(".py", "")
            for f in os.listdir(self.cogs_directory)
            if f.endswith(".py") and not f.startswith("_")
        ]

    def suggest_cog_name(self, cog_name: str, loaded: bool = True) -> Optional[str]:
        """Suggest a cog name based on available or loaded cogs."""
        cogs = (
            [cog.replace("cogs.", "") for cog in self.bot.extensions.keys()]
            if loaded
            else self.get_available_cogs()
        )
        matches = get_close_matches(cog_name, cogs, n=1)
        return matches[0] if matches else None

    async def prompt_confirmation(
        self, 
        interaction: Interaction, 
        action: ActionType, 
        cog_name: str
    ):
        """Show confirmation prompt for cog operations."""
        view = ConfirmView(interaction, self.bot, action, cog_name, self.owner_id)
        await interaction.response.send_message(
            f"Are you sure you want to {action} the cog `{cog_name}`?",
            view=view,
            ephemeral=True
        )

    @nextcord.slash_command(name="cog", description="Manage bot cogs")
    async def cog(self, interaction: Interaction):
        """Parent command for cog management."""
        pass

    @cog.subcommand(name="load", description="Load a cog")
    async def load_cog(self, interaction: Interaction, cog_name: str):
        """Load a specified cog."""
        if f"cogs.{cog_name}" in self.bot.extensions:
            suggestion = self.suggest_cog_name(cog_name, loaded=False)
            message = f"Cog `{cog_name}` is already loaded."
            if suggestion:
                message += f"\nDid you mean to load `{suggestion}`?"
            await interaction.response.send_message(message, ephemeral=True)
            return

        await self.prompt_confirmation(interaction, "load", cog_name)

    @cog.subcommand(name="unload", description="Unload a cog")
    async def unload_cog(self, interaction: Interaction, cog_name: str):
        """Unload a specified cog."""
        if f"cogs.{cog_name}" not in self.bot.extensions:
            suggestion = self.suggest_cog_name(cog_name, loaded=True)
            message = f"Cog `{cog_name}` is not loaded."
            if suggestion:
                message += f"\nDid you mean to unload `{suggestion}`?"
            await interaction.response.send_message(message, ephemeral=True)
            return

        await self.prompt_confirmation(interaction, "unload", cog_name)

    @cog.subcommand(name="reload", description="Reload a cog")
    async def reload_cog(self, interaction: Interaction, cog_name: str):
        """Reload a specified cog."""
        if f"cogs.{cog_name}" not in self.bot.extensions:
            suggestion = self.suggest_cog_name(cog_name, loaded=True)
            message = f"Cog `{cog_name}` is not loaded."
            if suggestion:
                message += f"\nDid you mean to reload `{suggestion}`?"
            await interaction.response.send_message(message, ephemeral=True)
            return

        await self.prompt_confirmation(interaction, "reload", cog_name)

    @cog.subcommand(name="list", description="List all cogs")
    async def list_cogs(self, interaction: Interaction):
        """List all available and loaded cogs."""
        loaded_cogs = [cog.replace("cogs.", "") for cog in self.bot.extensions.keys()]
        available_cogs = self.get_available_cogs()
        unloaded_cogs = [cog for cog in available_cogs if cog not in loaded_cogs]

        embed = Embed(title="Cog Status", color=Color.blue())
        embed.add_field(
            name="📥 Loaded Cogs", 
            value=", ".join(f"`{cog}`" for cog in loaded_cogs) or "None", 
            inline=False
        )
        embed.add_field(
            name="📤 Unloaded Cogs", 
            value=", ".join(f"`{cog}`" for cog in unloaded_cogs) or "None", 
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

def setup(bot: Bot):
    """Set up the CogManager cog."""
    if not OWNER_ID:
        print(Fore.YELLOW + "[WARN]: Owner ID not specified!")
    else:
        bot.add_cog(CogManager(bot, owner_id=OWNER_ID))
