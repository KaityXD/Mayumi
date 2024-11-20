import nextcord
import re


def create_embed(title, description, color=nextcord.Color.purple()):
    return nextcord.Embed(title=title, description=description, color=color)


def format_duration(duration_ms):
    seconds = duration_ms // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def check_same_voice_channel(inter: nextcord.Interaction) -> bool:
    if not inter.guild.voice_client:
        return False
    return inter.user.voice and inter.user.voice.channel == inter.guild.voice_client.channel

async def voice_channel_check(inter: nextcord.Interaction):
    if not check_same_voice_channel(inter):
        embed = create_embed("<a:9211092078964408931:1276525091588669531> ข้อผิดพลาด", "คุณต้องอยู่ในห้องเสียงเดียวกับบอทเพื่อใช้คำสั่งนี้", color=nextcord.Color.red())
        await inter.response.send_message(embed=embed)
        return False
    return True

def parse_duration(duration_str):
    time_regex = re.match(r"(\d+)([smh])", duration_str)
    if not time_regex:
        return None

    amount = int(time_regex.group(1))
    unit = time_regex.group(2)

    if unit == "s":
        return amount
    elif unit == "m":
        return amount * 60
    elif unit == "h":
        return amount * 3600

    return None
