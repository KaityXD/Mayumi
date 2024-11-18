import nextcord
from nextcord.ext import commands
from nextcord import Interaction, Embed
import psutil
import platform
from datetime import datetime

class StatusInfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.utcnow()

    def _get_bot_uptime(self):
        uptime = datetime.utcnow() - self.start_time
        days, remainder = divmod(int(uptime.total_seconds()), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}d {hours}h {minutes}m {seconds}s"

    def _get_system_stats(self):
        return {
            'cpu_usage': psutil.cpu_percent(),
            'memory_usage': psutil.virtual_memory().percent,
            'total_memory': f"{psutil.virtual_memory().total / (1024 ** 3):.2f} GB"
        }

    @nextcord.slash_command(name="status", description="Get comprehensive bot and system status")
    async def slash_status(self, interaction: Interaction):
        try:
            system_stats = self._get_system_stats()
            
            embed = Embed(
                title="🚀 Bot Status",
                description="🔍 Detailed bot and system information",
                color=nextcord.Color.green()
            )
            embed.add_field(name="⏰ Uptime", value=self._get_bot_uptime(), inline=False)
            embed.add_field(name="💻 CPU Usage", value=f"{system_stats['cpu_usage']}%", inline=True)
            embed.add_field(name="🧠 Memory Usage", value=f"{system_stats['memory_usage']}%", inline=True)
            embed.add_field(name="💾 Total Memory", value=system_stats['total_memory'], inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception:
            await interaction.response.send_message("❌ An error occurred while fetching status.", ephemeral=True)

    @nextcord.slash_command(name="info", description="Get comprehensive bot information")
    async def slash_info(self, interaction: Interaction):
        try:
            embed = Embed(
                title="🤖 Bot Information",
                color=nextcord.Color.blue()
            )
            
            embed.add_field(name="📛 Bot Name", value=self.bot.user.name, inline=True)
            embed.add_field(name="🆔 Bot ID", value=self.bot.user.id, inline=True)
            
            embed.add_field(name="🐍 Python Version", value=platform.python_version(), inline=True)
            embed.add_field(name="🔧 Nextcord Version", value=nextcord.__version__, inline=True)
            embed.add_field(name="💻 Platform", value=platform.platform(), inline=False)
            
            embed.add_field(name="🏰 Servers", value=len(self.bot.guilds), inline=True)
            embed.add_field(name="👥 Users", value=len(set(self.bot.users)), inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception:
            await interaction.response.send_message("❌ An error occurred while fetching bot info.", ephemeral=True)

    @commands.command(name="status")
    async def status(self, ctx: commands.Context):
        await ctx.send(f"🚀 Bot is running. Uptime: {self._get_bot_uptime()}")

    @commands.command(name="info")
    async def info(self, ctx: commands.Context):
        await ctx.send(f"🤖 Bot Name: {self.bot.user.name}\n🏰 Servers: {len(self.bot.guilds)}")

def setup(bot):
    bot.add_cog(StatusInfoCog(bot))
