import discord
from bots import music_bot
from discord.ext import commands
import sys
from config.settings import DISCORD_TOKEN

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

    for guild in bot.guilds:
        print(f'Connected to guild: {guild.name}')
        await bot.tree.sync(guild=guild)

try:
    bot.run(DISCORD_TOKEN)
except Exception as e:
    print(f"Error occurred: {e}")
    sys.exit(1)
