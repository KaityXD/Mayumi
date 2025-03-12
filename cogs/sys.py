import platform
import time
import psutil
import datetime
import logging
from typing import Dict, Any
from collections import namedtuple

import nextcord
from nextcord.ext import commands

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system_info.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Custom type for system statistics
SystemStats = namedtuple('SystemStats', ['cpu', 'memory', 'disk', 'network', 'boot_time'])

class SystemInfoConfig:
    """Configuration for SystemInfo cog"""
    REFRESH_RATE = 60  # seconds
    EMBED_COLORS = {
        "main": 0x2b2d31,      # Dark theme discord color
        "success": 0x57F287,   # Green
        "warning": 0xFEE75C,   # Yellow
        "error": 0xED4245,     # Red
        "info": 0x5865F2       # Blurple
    }
    EMOJIS = {
        "ping": "🏓",
        "cpu": "💻",
        "ram": "📊",
        "disk": "💾",
        "network": "🌐",
        "uptime": "⏰",
        "python": "🐍",
        "nextcord": "📡",
        "os": "⚙️",
        "loading": "🔄"
    }

class SystemInfo(commands.Cog):
    """
    A feature-rich system information cog that provides detailed statistics
    about the bot and the system it's running on.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_stats: Dict[str, Any] = {}
        self._start_time = time.time()
        logger.info("SystemInfo cog initialized")

    def _get_system_stats(self) -> SystemStats:
        """Collect system statistics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())

            return SystemStats(
                cpu=cpu_percent,
                memory=memory,
                disk=disk,
                network=network,
                boot_time=boot_time
            )
        except Exception as e:
            logger.error(f"Error collecting system stats: {str(e)}")
            return None

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime into a human-readable string"""
        delta = datetime.timedelta(seconds=int(seconds))
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        if seconds: parts.append(f"{seconds}s")

        return " ".join(parts)

    def _format_bytes(self, bytes: int) -> str:
        """Format bytes into human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024
        return f"{bytes:.2f} PB"

    @commands.command()
    async def ping(self, ctx: commands.Context):
        """Get the bot's current websocket latency."""
        try:
            start_time = time.perf_counter()
            message = await ctx.send("Pinging...")
            end_time = time.perf_counter()

            duration = (end_time - start_time) * 1000
            ws_latency = round(self.bot.latency * 1000)

            embed = nextcord.Embed(
                title=f"{SystemInfoConfig.EMOJIS['ping']} Pong!",
                color=SystemInfoConfig.EMBED_COLORS['main']
            )

            embed.add_field(
                name="Websocket Latency",
                value=f"```{ws_latency}ms```",
                inline=True
            )
            embed.add_field(
                name="API Latency",
                value=f"```{duration:.2f}ms```",
                inline=True
            )

            await message.edit(content=None, embed=embed)
            logger.info(f"Ping command executed - WS: {ws_latency}ms, API: {duration:.2f}ms")

        except Exception as e:
            logger.error(f"Error in ping command: {str(e)}")
            await ctx.send("❌ An error occurred while checking ping.")

    @commands.command(aliases=['sys', 'system', 'about'])
    async def stats(self, ctx: commands.Context):
        """Display detailed system statistics and bot information."""
        try:
            async with ctx.typing():
                stats = self._get_system_stats()

                if not stats:
                    raise Exception("Failed to collect system statistics")

                # Create the main embed
                embed = nextcord.Embed(
                    title="📊 System Statistics",
                    description="Detailed system and bot information",
                    color=SystemInfoConfig.EMBED_COLORS['main'],
                    timestamp=datetime.datetime.utcnow()
                )

                # Bot Information
                bot_info = (
                    f"{SystemInfoConfig.EMOJIS['uptime']} **Uptime:** {self._format_uptime(time.time() - self._start_time)}\n"
                    f"{SystemInfoConfig.EMOJIS['python']} **Python:** v{platform.python_version()}\n"
                    f"{SystemInfoConfig.EMOJIS['nextcord']} **Nextcord:** v{nextcord.__version__}\n"
                    f"{SystemInfoConfig.EMOJIS['os']} **OS:** {platform.system()} {platform.release()}"
                )
                embed.add_field(name="Bot Information", value=bot_info, inline=False)

                # System Resources
                cpu_bar = self._create_progress_bar(stats.cpu)
                memory_bar = self._create_progress_bar(stats.memory.percent)
                disk_bar = self._create_progress_bar(stats.disk.percent)

                system_resources = (
                    f"{SystemInfoConfig.EMOJIS['cpu']} **CPU Usage:**\n{cpu_bar} {stats.cpu:.1f}%\n\n"
                    f"{SystemInfoConfig.EMOJIS['ram']} **Memory Usage:**\n{memory_bar} {stats.memory.percent:.1f}%\n"
                    f"```{self._format_bytes(stats.memory.used)}/{self._format_bytes(stats.memory.total)}```\n"
                    f"{SystemInfoConfig.EMOJIS['disk']} **Disk Usage:**\n{disk_bar} {stats.disk.percent:.1f}%\n"
                    f"```{self._format_bytes(stats.disk.used)}/{self._format_bytes(stats.disk.total)}```"
                )
                embed.add_field(name="System Resources", value=system_resources, inline=False)

                # Network Statistics
                network_stats = (
                    f"**Sent:** {self._format_bytes(stats.network.bytes_sent)}\n"
                    f"**Received:** {self._format_bytes(stats.network.bytes_recv)}"
                )
                embed.add_field(
                    name=f"{SystemInfoConfig.EMOJIS['network']} Network Statistics",
                    value=network_stats,
                    inline=True
                )

                # System Uptime
                system_uptime = self._format_uptime(time.time() - stats.boot_time.timestamp())
                embed.add_field(
                    name=f"{SystemInfoConfig.EMOJIS['uptime']} System Uptime",
                    value=f"```{system_uptime}```",
                    inline=True
                )

                # Footer
                embed.set_footer(
                    text=f"Requested by {ctx.author}",
                    icon_url=ctx.author.avatar.url if ctx.author.avatar else None
                )

                await ctx.send(embed=embed)
                logger.info(f"Stats command executed by {ctx.author}")

        except Exception as e:
            logger.error(f"Error in stats command: {str(e)}")
            error_embed = nextcord.Embed(
                title="❌ Error",
                description="An error occurred while fetching system statistics.",
                color=SystemInfoConfig.EMBED_COLORS['error']
            )
            await ctx.send(embed=error_embed)

    def _create_progress_bar(self, percent: float, length: int = 10) -> str:
        """Create a visual progress bar"""
        filled = int(percent / 100 * length)
        empty = length - filled
        bar = '▰' * filled + '▱' * empty
        return bar

    @commands.command()
    async def uptime(self, ctx: commands.Context):
        """Display the bot's uptime in a fancy embed."""
        try:
            uptime = self._format_uptime(time.time() - self._start_time)

            embed = nextcord.Embed(
                title=f"{SystemInfoConfig.EMOJIS['uptime']} Bot Uptime",
                description=f"```{uptime}```",
                color=SystemInfoConfig.EMBED_COLORS['main'],
                timestamp=datetime.datetime.utcnow()
            )

            started_at = datetime.datetime.fromtimestamp(self._start_time)
            embed.add_field(
                name="Started At",
                value=f"```{started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}```",
                inline=False
            )

            embed.set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else None
            )

            await ctx.send(embed=embed)
            logger.info(f"Uptime command executed by {ctx.author}")

        except Exception as e:
            logger.error(f"Error in uptime command: {str(e)}")
            await ctx.send("❌ An error occurred while fetching uptime information.")

def setup(bot: commands.Bot):
    """Set up the SystemInfo cog."""
    bot.add_cog(SystemInfo(bot))
