import nextcord
from nextcord.ext import commands
from nextcord import SlashOption
from collections import defaultdict
import mafic
from mafic import SearchType
import asyncio
import random
from utils.music_utils import create_embed, format_duration, voice_channel_check
from utils.config import LAVALINK_PORT
from utils.config import LAVALINK_HOST
from utils.config import LAVALINK_PASSWORD

class GuildMusicState:
    def __init__(self):
        self.queue = []
        self.current_track = None
        self.volume = 100
        self.disconnect_task = None
        self.autoplay = False

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.pool = mafic.NodePool(self.bot)
        self.bot.guild_music_states = defaultdict(GuildMusicState)
        self.bot.loop.create_task(self.add_nodes())

    async def add_nodes(self):
        await self.bot.pool.create_node(
            host=LAVALINK_HOST,
            port=LAVALINK_PORT,
            label="MAIN",
            password=LAVALINK_PASSWORD,
        )

    @nextcord.slash_command(name="play", description="[🌺] Play some music")
    async def play(self, inter: nextcord.Interaction, query: str = SlashOption(description="Tracks name or url")):
        await inter.response.defer()

        if not inter.user.voice:
            embed = create_embed("<a:9211092078964408931:1276525091588669531>", "you need to join voice chat to use this command", color=nextcord.Color.red())
            return await inter.followup.send(embed=embed)

        guild_state = self.bot.guild_music_states[inter.guild.id]
        if not inter.guild.voice_client:
            player = await inter.user.voice.channel.connect(cls=mafic.Player)
        else:
            player = inter.guild.voice_client
            if player.channel != inter.user.voice.channel:
                embed = create_embed("<a:9211092078964408931:1276525091588669531>", "you need to be in same voice channel as bot", color=nextcord.Color.red())
                return await inter.followup.send(embed=embed)

        try:
            tracks = await player.fetch_tracks(query, search_type=SearchType.YOUTUBE_MUSIC)

        except Exception as e:
            embed = create_embed("<a:9211092078964408931:1276525091588669531>", f"error while searching traks: {str(e)}", color=nextcord.Color.red())
            return await inter.followup.send(embed=embed)

        if not tracks:
            embed = create_embed("<a:9211092078964408931:1276525091588669531> not found", "searched tracks is nowhere to be found", color=nextcord.Color.red())
            return await inter.followup.send(embed=embed)

        if isinstance(tracks, mafic.Playlist):
            playlist = tracks
            for track in playlist.tracks:
                guild_state.queue.append(track)
            if not guild_state.current_track:
                guild_state.current_track = playlist.tracks[0]
                await player.play(guild_state.current_track)


            embed = create_embed("", f"> **<a:experience:1276521604431482900> [{playlist.name}]({playlist.tracks[0].uri if playlist.tracks else ''})**")
            embed.set_author(name="🎵 | Added to queue", icon_url=self.bot.user.avatar.url)
            embed.set_thumbnail(url=playlist.tracks[0].artwork_url if playlist.tracks else None)
            embed.add_field(name="<:enchanted_book:1287070850633171026> Playlist Info", value=f"┗ **{inter.user.mention}** ``{len(playlist.tracks)} traks from playlist``")
            embed.set_footer(text=f"🌺 {self.bot.user.name} | By KaiTy_Ez")
        else:
            track = tracks[0]
            if not guild_state.current_track:
                guild_state.current_track = track
                await player.play(track)
                status = "🎵 | Now playing"
            else:
                guild_state.queue.append(track)
                status = "🎵 | Added Track"

            embed = create_embed("", f"> **<a:experience:1276521604431482900> [{track.title}]({track.uri})**")
            embed.set_author(name=status, icon_url=self.bot.user.avatar.url)
            embed.set_thumbnail(url=track.artwork_url)
            embed.add_field(name="<:enchanted_book:1287070850633171026> Tracks info", value=f"┗ **{track.author}** ``{format_duration(track.length)}``")
            embed.set_footer(text=f"🌺 {self.bot.user.name} | By KaiTy_Ez")

        await inter.followup.send(embed=embed)
        await player.set_volume(guild_state.volume)

        if guild_state.disconnect_task:
            guild_state.disconnect_task.cancel()
            guild_state.disconnect_task = None


    @nextcord.slash_command( description="[🌺] Toggle auto play")
    async def autoplay(self, inter: nextcord.Interaction):
        guild_state = self.bot.guild_music_states[inter.guild.id]
        guild_state.autoplay = not guild_state.autoplay

        status = "On" if guild_state.autoplay else "Off"
        embed = create_embed("", f"Autoplay is now {status}")
        await inter.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_track_end(self, event):
        guild_id = event.player.guild.id
        await self.play_next(guild_id)

    async def play_next(self, guild_id):
        guild_state = self.bot.guild_music_states[guild_id]
        player = self.bot.get_guild(guild_id).voice_client

        if guild_state.queue:
            next_track = guild_state.queue.pop(0)
            guild_state.current_track = next_track
            await player.play(next_track)
        else:
            guild_state.current_track = None
            if guild_state.autoplay:
                tracks = await player.fetch_tracks("lofi lee")
                if tracks:
                    next_track = random.choice(tracks)
                    guild_state.current_track = next_track
                    await player.play(next_track)
            else:
                guild_state.disconnect_task = asyncio.create_task(self.disconnect_after_timeout(guild_id))

    async def disconnect_after_timeout(self, guild_id):
        await asyncio.sleep(30)
        guild = self.bot.get_guild(guild_id)
        if guild and guild.voice_client:
            await guild.voice_client.disconnect()
        self.bot.guild_music_states[guild_id].disconnect_task = None

    @nextcord.slash_command( description="[🌺]  Temp stop the song")
    async def pause(self, inter: nextcord.Interaction):
        if not await voice_channel_check(inter):
            return
        if not inter.guild.voice_client:
            embed = create_embed("<a:9211092078964408931:1276525091588669531>", "Cannot join voice channel", color=nextcord.Color.red())
            return await inter.response.send_message(embed=embed)

        player = inter.guild.voice_client
        if player.paused:
            embed = create_embed("", "Song is already paused", color=0xf39c12)
            return await inter.response.send_message(embed=embed)

        await player.pause()
        embed = create_embed("", "paused song")
        await inter.response.send_message(embed=embed)

    @nextcord.slash_command( description="[🌺] Node infomation")
    async def node(self, inter: nextcord.Interaction):
        await inter.response.defer()

        try:
            stats = self.bot.pool.nodes[0].stats
        except Exception as e:
            embed = create_embed("❌", f"Error while fetching info: {str(e)}", color=0xe74c3c)
            return await inter.followup.send(embed=embed)

        uptime = str(stats.uptime)
        memory_used = stats.memory.used / 1024 / 1024
        memory_free = stats.memory.free / 1024 / 1024
        memory_allocated = stats.memory.allocated / 1024 / 1024
        memory_reservable = stats.memory.reservable / 1024 / 1024
        cpu_load = stats.cpu.system_load
        lavalink_load = stats.cpu.lavalink_load
        player_count = stats.player_count
        playing_player_count = stats.playing_player_count

        embed = create_embed("🔍Lavalink Node Status", f"""
```- Uptime: {uptime}
- Memory Used: {memory_used:.2f}/{memory_allocated:.2f} MiB
- CPU Load: {cpu_load:.2f}%
- Players Connected: {player_count}
- Playing Players: {playing_player_count}```
""")
        embed.set_author(name="Node Status", icon_url=self.bot.user.avatar.url)
        embed.set_footer(text=f"🌺 {self.bot.user.name} | By KaiTy_Ez")

        await inter.followup.send(embed=embed)

    @nextcord.slash_command( description="[🌺] Set the volume")
    async def volume(self, inter: nextcord.Interaction, volume: int = SlashOption(description="volume (1-100)")):
        if not await voice_channel_check(inter):
            return
        if not inter.guild.voice_client:
            embed = create_embed("<a:9211092078964408931:1276525091588669531>", "Im not in voice channel", color=nextcord.Color.red())
            return await inter.response.send_message(embed=embed)

        if volume < 0 or volume > 100:
            embed = create_embed("<a:9211092078964408931:1276525091588669531>", "volume need to be between 0 to 100", color=nextcord.Color.blue)
            return await inter.response.send_message(embed=embed)

        guild_state = self.bot.guild_music_states[inter.guild.id]
        guild_state.volume = volume
        player = inter.guild.voice_client
        await player.set_volume(volume)
        embed = create_embed("", f"volume now set to {volume}%")
        await inter.response.send_message(embed=embed)

    @nextcord.slash_command( description="[🌺] Disconnect bot from vc")
    async def disconnect(self, inter: nextcord.Interaction):
        if not await voice_channel_check(inter):
            return
        if not inter.guild.voice_client:
            embed = create_embed("<a:9211092078964408931:1276525091588669531>", "Im not in voice channel", color=nextcord.Color.red())
            return await inter.response.send_message(embed=embed)

        guild_state = self.bot.guild_music_states[inter.guild.id]
        guild_state.queue.clear()
        guild_state.current_track = None
        await inter.guild.voice_client.disconnect()
        embed = create_embed("", "Disconnected")
        await inter.response.send_message(embed=embed)

    @nextcord.slash_command( description="[🌺] Check queue")
    async def queue(self, inter: nextcord.Interaction):
        if not await voice_channel_check(inter):
                return
        await inter.response.defer()
        if not inter.guild.voice_client:
            embed = create_embed("<a:9211092078964408931:1276525091588669531>", "Im not in voice channel", color=nextcord.Color.red())
            return await inter.response.send_message(embed=embed)

        guild_state = self.bot.guild_music_states[inter.guild.id]
        if not guild_state.current_track and not guild_state.queue:
            embed = create_embed("📋", "No Tracks in queue", color=0xf39c12)
            return await inter.response.send_message(embed=embed)

        embed = create_embed("📋 Current Queue", "")
        if guild_state.current_track:
            embed.add_field(name="🎵 Playing", value=f"[{guild_state.current_track.title}]({guild_state.current_track.uri}) | `{format_duration(guild_state.current_track.length)}`", inline=False)

        if guild_state.queue:
            queue_list = "\n".join([f"`{i+1}.` [{track.title}]({track.uri}) | `{format_duration(track.length)}`" for i, track in enumerate(guild_state.queue[:10])])
            embed.add_field(name="<a:soon:1286713974574022757> Next", value=queue_list, inline=False)
        if len(guild_state.queue) > 10:
            embed.set_footer(text=f"Show 10 Tacks of {len(guild_state.queue)} Tracks")

        await inter.followup.send(embed=embed)

    @nextcord.slash_command( description="[🌺] Skip playing song")
    async def skip(self, inter: nextcord.Interaction):
        if not await voice_channel_check(inter):
            return
        if not inter.guild.voice_client:
            embed = create_embed("<a:9211092078964408931:1276525091588669531> error", "In not in voice channel", color=nextcord.Color.red())
            return await inter.response.send_message(embed=embed)

        guild_state = self.bot.guild_music_states.get(inter.guild.id)
        player = inter.guild.voice_client

        if not guild_state or not guild_state.current_track:
            embed = create_embed("", "Not skipped, no tracks are playing", color=nextcord.Color.orange())
            return await inter.response.send_message(embed=embed)

        embed = create_embed("", "Skipped", color=nextcord.Color.green())
        await inter.response.send_message(embed=embed)

        await player.stop()

    @nextcord.slash_command( description="[🌺] Resume paused song")
    async def resume(self, inter: nextcord.Interaction):
        if not await voice_channel_check(inter):
            return
        if not inter.guild.voice_client:
            embed = create_embed("<a:9211092078964408931:1276525091588669531>", "Im not in voice channel", color=nextcord.Color.red())
            return await inter.response.send_message(embed=embed)

        player = inter.guild.voice_client
        if not player.paused:
            embed = create_embed("", "No Song is paused", color=0xf39c12)
            return await inter.response.send_message(embed=embed)

        await player.resume()
        embed = create_embed("", "Now enjoy your songs")
        await inter.response.send_message(embed=embed)

    @nextcord.slash_command( description="[🌺] Stop and wipe queue")
    async def stop(self, inter: nextcord.Interaction):
        if not await voice_channel_check(inter):
            return
        if not inter.guild.voice_client:
            embed = create_embed("<a:9211092078964408931:1276525091588669531>", "IM not in voice channel", color=nextcord.Color.red())
            return await inter.response.send_message(embed=embed)

        guild_state = self.bot.guild_music_states[inter.guild.id]
        player = inter.guild.voice_client
        await player.stop()
        guild_state.queue.clear()
        guild_state.current_track = None
        embed = create_embed("", "Wiped queue and stop songs")
        await inter.response.send_message(embed=embed)
def setup(bot):
    if LAVALINK_PORT and LAVALINK_HOST and LAVALINK_PASSWORD:
      bot.add_cog(MusicCog(bot))
    else:
      print("[WARN]: Cannot load music features due to improper configuration!")
