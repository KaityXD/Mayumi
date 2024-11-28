import nextcord
from nextcord.ext import commands

class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx, *, command_name: str = None):
        """
        Custom dynamic help command.
        If no command is provided, it lists all commands.
        If a specific command is provided, it shows detailed info.
        """
        if command_name:
            # Show detailed help for a specific command
            command = self.bot.get_command(command_name)
            if not command:
                await ctx.send(f"No command found with name `{command_name}`.")
                return
            
            embed = nextcord.Embed(
                title=f"Help: {command.name}",
                description=command.help or "No description provided.",
                color=nextcord.Color.blue()
            )
            if command.aliases:
                embed.add_field(
                    name="Aliases",
                    value=", ".join(command.aliases),
                    inline=False
                )
            embed.add_field(
                name="Usage",
                value=f"`{ctx.prefix}{command.usage or command.name}`",
                inline=False
            )
            await ctx.send(embed=embed)
        else:
            # Show a list of all commands
            embed = nextcord.Embed(
                title="Help - List of Commands",
                description="Use `help <command>` to get more info on a specific command.",
                color=nextcord.Color.blue()
            )

            for cog_name, cog in self.bot.cogs.items():
                commands_list = cog.get_commands()
                command_names = [cmd.name for cmd in commands_list if not cmd.hidden]
                if command_names:
                    embed.add_field(
                        name=cog_name,
                        value=", ".join(command_names),
                        inline=False
                    )
            
            # Add uncategorized commands
            uncategorized = [cmd.name for cmd in self.bot.commands if not cmd.cog_name and not cmd.hidden]
            if uncategorized:
                embed.add_field(
                    name="Uncategorized Commands",
                    value=", ".join(uncategorized),
                    inline=False
                )
            
            await ctx.send(embed=embed)

# Add the Cog to your bot
def setup(bot):
    bot.add_cog(HelpCommand(bot))

