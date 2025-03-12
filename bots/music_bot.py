import discord
from discord.ext import commands
from commands import music_commands
from config.settings import DISCORD_TOKEN

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user.name}')

# Register music commands
music_commands.register_commands(bot)

if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print('Discord token not found')