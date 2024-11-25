import os
from typing import Optional, List, Literal
from dataclasses import dataclass
import nextcord
from nextcord import Interaction, Embed, Color
from nextcord.ext import commands
from nextcord.ext.commands import Bot, Context
from difflib import get_close_matches
from colorama import Fore, init
from utils.config import OWNER_ID

ActionType = Literal["load", "unload", "reload"]
init(autoreset=True)

@dataclass
class CogOperation:
    success: bool
    message: str
    error: Optional[Exception] = None

class CogManager(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.cogs_directory = "cogs"

    def get_available_cogs(self) -> List[str]:
        if not os.path.exists(self.cogs_directory):
            return []

        return [
            f.replace(".py", "")
            for f in os.listdir(self.cogs_directory)
            if f.endswith(".py") and not f.startswith("_")
        ]

    def suggest_cog_name(self, cog_name: str, loaded: bool = True) -> Optional[str]:
        cogs = (
            [cog.replace("cogs.", "") for cog in self.bot.extensions.keys()]
            if loaded
            else self.get_available_cogs()
        )
        matches = get_close_matches(cog_name, cogs, n=1)
        return matches[0] if matches else None

    def is_owner(self, user_id: int) -> bool:
        return user_id == OWNER_ID

    async def process_cog_operation(
        self, 
        ctx: Context, 
        action: ActionType, 
        cog_name: str,
        user_id: int
    ) -> CogOperation:
        if not self.is_owner(user_id):
            return CogOperation(
                success=False, 
                message="Only the bot owner can perform this operation."
            )

        try:
            cog_path = f"cogs.{cog_name}"
            if action == "load":
                self.bot.load_extension(cog_path)
            elif action == "unload":
                self.bot.unload_extension(cog_path)
            else:  # reload
                self.bot.reload_extension(cog_path)

            return CogOperation(
                success=True,
                message=f"{action.capitalize()}ed cog: `{cog_name}` successfully."
            )
        except Exception as e:
            return CogOperation(
                success=False,
                message=f"Failed to {action} cog `{cog_name}`",
                error=e
            )

    @commands.command(name="load")
    async def prefix_load_cog(self, ctx: Context, cog_name: str):
        result = await self.process_cog_operation(ctx, "load", cog_name, ctx.author.id)
        await ctx.reply(result.message)
        if result.error:
            await ctx.reply(f"Error: {result.error}")

    @commands.command(name="unload")
    async def prefix_unload_cog(self, ctx: Context, cog_name: str):
        result = await self.process_cog_operation(ctx, "unload", cog_name, ctx.author.id)
        await ctx.reply(result.message)
        if result.error:
            await ctx.reply(f"Error: {result.error}")

    @commands.command(name="reload")
    async def prefix_reload_cog(self, ctx: Context, cog_name: str):
        result = await self.process_cog_operation(ctx, "reload", cog_name, ctx.author.id)
        await ctx.reply(result.message)
        if result.error:
            await ctx.reply(f"Error: {result.error}")

    @commands.command(name="cogs")
    async def prefix_list_cogs(self, ctx: Context):
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

        await ctx.reply(embed=embed)

    @nextcord.slash_command(name="cog", description="Manage bot cogs")
    async def cog(self, interaction: Interaction):
        pass

    @cog.subcommand(name="load", description="Load a cog")
    async def slash_load_cog(self, interaction: Interaction, cog_name: str):
        result = await self.process_cog_operation(None, "load", cog_name, interaction.user.id)
        await interaction.reply(result.message, ephemeral=True)
        if result.error:
            await interaction.followup.send(f"Error: {result.error}")

    @cog.subcommand(name="unload", description="Unload a cog")
    async def slash_unload_cog(self, interaction: Interaction, cog_name: str):
        result = await self.process_cog_operation(None, "unload", cog_name, interaction.user.id)
        await interaction.reply(result.message, ephemeral=True)
        if result.error:
            await interaction.followup.send(f"Error: {result.error}")

    @cog.subcommand(name="reload", description="Reload a cog")
    async def slash_reload_cog(self, interaction: Interaction, cog_name: str):
        result = await self.process_cog_operation(None, "reload", cog_name, interaction.user.id)
        await interaction.reply(result.message, ephemeral=True)
        if result.error:
            await interaction.followup.send(f"Error: {result.error}")

    @cog.subcommand(name="list", description="List all cogs")
    async def slash_list_cogs(self, interaction: Interaction):
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

        await interaction.reply(embed=embed)

def setup(bot: Bot):
    if not OWNER_ID: print(Fore.YELLOW+"[WARN]: Owner Id is empty you may notnuse manager commands")
    bot.add_cog(CogManager(bot))
