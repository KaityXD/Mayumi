import os
import nextcord
import asyncio
import sys
from nextcord.ext import commands
from utils.config import BOT_TOKEN
from nextcord import *
from colorama import init, Fore
init(autoreset=True)

# test pr

bot = commands.Bot(intents=Intents.all(), help_command=None)

@bot.event
async def on_ready():


    total_slash_commands = len(bot.get_application_commands())
    total_cogs = len(bot.cogs)
    print(Fore.LIGHTGREEN_EX + "\n-----------[Kaity Ez]-----------")
    print(Fore.GREEN + "\n🚀", Fore.BLUE + bot.user.name, Fore.GREEN + "is online!")
    print(Fore.GREEN + "🔧 Bot ID:", Fore.YELLOW + f"{bot.user.id}")
    print(Fore.GREEN + "🌐 Connected to", Fore.YELLOW + f"{len(bot.guilds)}", Fore.GREEN + "servers")
    print(Fore.GREEN + "🤖 Running on", Fore.BLUE + "Nextcord", Fore.YELLOW + f"v{nextcord.__version__}", Fore.GREEN + "")
    print(Fore.GREEN + "📁 Loaded Cogs:", Fore.YELLOW + f"{total_cogs}")
    print(Fore.GREEN + "⚡ Slash Commands:", Fore.YELLOW + f"{total_slash_commands}")

loaded_cogs = 0

for filename in os.listdir('./cogs'):
    if filename.endswith('_cog.py'):
        module = f'cogs.{filename[:-3]}'
        bot.load_extension(module)
        loaded_cogs += 1
        print(Fore.GREEN + "[loaded]", Fore.LIGHTBLUE_EX + module)

print(Fore.YELLOW + f"\nTotal Cogs Loaded: {loaded_cogs}")

if __name__ == '__main__':
    if BOT_TOKEN:
      bot.run(BOT_TOKEN)
    else:
      print(Fore.RED + "[ERR]: Bot token not specified!")
      sys.exit()
