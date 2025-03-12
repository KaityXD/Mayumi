import nextcord
from nextcord.ext import commands
from nextcord.ui import View, Button
from typing import Optional
import datetime

class HelpMenu(View):
    def __init__(self, ctx, bot, commands_per_page=4):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.bot = bot
        self.commands_per_page = commands_per_page
        self.current_page = 0
        
        # Sort and organize commands and groups
        self.all_commands = []
        for cmd in bot.commands:
            if isinstance(cmd, commands.Group):
                # Add group command first
                self.all_commands.append((cmd, True))  # True indicates it's a group
                # Add subcommands
                for subcmd in cmd.commands:
                    self.all_commands.append((subcmd, False))  # False indicates it's a subcommand
            else:
                self.all_commands.append((cmd, None))  # None indicates it's a regular command

        self.max_pages = (len(self.all_commands) - 1) // self.commands_per_page + 1
        self.previous.disabled = True
        self.next.disabled = self.max_pages <= 1

    def format_command(self, cmd, is_group):
        if is_group is True:  # Group command
            return f"📁 `{cmd.name}`"
        elif is_group is False:  # Subcommand
            return f"└─ `{cmd.parent.name} {cmd.name}`"
        else:  # Regular command
            return f"📄 `{cmd.name}`"

    async def update_embed(self):
        start = self.current_page * self.commands_per_page
        end = start + self.commands_per_page
        current_commands = self.all_commands[start:end]
        
        embed = nextcord.Embed(
            title="Command Help",
            description="Use `!help <command>` for detailed help\nUse `!help <group> <subcommand>` for subcommand help",
            color=nextcord.Color.blue()
        )
        
        for cmd, is_group in current_commands:
            name = self.format_command(cmd, is_group)
            value = cmd.help or "No description provided."
            
            if isinstance(cmd, commands.Group):
                value += f"\n*Has {len(cmd.commands)} subcommands*"
                
            embed.add_field(name=name, value=value, inline=False)
            
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages}")
        return embed

    @nextcord.ui.button(label="◀", style=nextcord.ButtonStyle.blurple)
    async def previous(self, button: Button, interaction: nextcord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This menu is not for you!", ephemeral=True)
        
        self.current_page = max(0, self.current_page - 1)
        self.update_button_states()
        await interaction.response.edit_message(embed=await self.update_embed(), view=self)

    @nextcord.ui.button(label="▶", style=nextcord.ButtonStyle.blurple)
    async def next(self, button: Button, interaction: nextcord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This menu is not for you!", ephemeral=True)
        
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        self.update_button_states()
        await interaction.response.edit_message(embed=await self.update_embed(), view=self)

    def update_button_states(self):
        self.previous.disabled = self.current_page == 0
        self.next.disabled = self.current_page == self.max_pages - 1

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command('help')  # Remove default help command

    def get_command_help(self, command):
        embed = nextcord.Embed(
            title=f"Help: {command.qualified_name}",
            color=nextcord.Color.blue()
        )

        # Command description
        embed.add_field(
            name="Description",
            value=command.help or "No description provided.",
            inline=False
        )

        # Usage
        usage = f"!{command.qualified_name}"
        if command.signature:
            usage += f" {command.signature}"
        embed.add_field(name="Usage", value=f"`{usage}`", inline=False)

        # If it's a group command, show subcommands
        if isinstance(command, commands.Group):
            subcommands = "\n".join(
                f"`{subcmd.name}` - {subcmd.help or 'No description'}"
                for subcmd in command.commands
            )
            if subcommands:
                embed.add_field(name="Subcommands", value=subcommands, inline=False)

        # Show aliases if any
        if command.aliases:
            embed.add_field(
                name="Aliases",
                value=", ".join(f"`{alias}`" for alias in command.aliases),
                inline=False
            )

        # Show permissions if any
        if command.checks:
            perms = []
            for check in command.checks:
                if hasattr(check, "__qualname__"):
                    perm = check.__qualname__.split('.')[0]
                    perms.append(perm.replace('has_', '').replace('_', ' ').title())
            if perms:
                embed.add_field(name="Required Permissions", value=", ".join(perms), inline=False)

        embed.set_footer(text="<> = Required | [] = Optional")
        return embed

    @commands.command(name="help")
    async def help_command(self, ctx, group: Optional[str] = None, subcommand: Optional[str] = None):
        """Shows help for all commands or specific commands/groups"""
        # No arguments - show general help
        if not group:
            menu = HelpMenu(ctx, self.bot)
            return await ctx.send(embed=await menu.update_embed(), view=menu)

        # Find the command/group
        if subcommand:
            # Looking for a subcommand
            group_cmd = self.bot.get_command(group)
            if not group_cmd or not isinstance(group_cmd, commands.Group):
                return await ctx.send(f"❌ Command group `{group}` not found.")
            
            cmd = group_cmd.get_command(subcommand)
            if not cmd:
                return await ctx.send(f"❌ Subcommand `{subcommand}` not found in `{group}`.")
        else:
            # Looking for a command/group
            cmd = self.bot.get_command(group)
            if not cmd:
                return await ctx.send(f"❌ Command `{group}` not found.")

        # Show help for the specific command/subcommand
        await ctx.send(embed=self.get_command_help(cmd))

    @help_command.error
    async def help_command_error(self, ctx, error):
        if isinstance(error, commands.CommandError):
            await ctx.send(f"❌ An error occurred: {str(error)}")

def setup(bot):
    bot.add_cog(HelpCog(bot))

