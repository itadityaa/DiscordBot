import discord
from discord.ext import tasks, commands
import sqlite3
from datetime import datetime, timedelta
from profanity_check import predict

# Connect to SQLite database
conn = sqlite3.connect('moderator_bot.db')
c = conn.cursor()

# Create tables if they don't exist
c.execute('''CREATE TABLE IF NOT EXISTS warnings
            (guild_id TEXT NOT NULL, user_id TEXT NOT NULL, warnings INTEGER, PRIMARY KEY (guild_id, user_id))''')
conn.commit()

# Set up the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Check for idle users every minute
@tasks.loop(minutes=1)
async def check_idle_users():
    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot and member.status == discord.Status.idle:
                last_activity = member.activity.start if member.activity else datetime.now()
                if datetime.now() - last_activity > timedelta(minutes=20):
                    await member.kick(reason="Idle for more than 20 minutes.")
                    print(f"Kicked {member.name} from {guild.name} for being idle.")

# Check for profanity in messages
@bot.event
async def on_message(message):
    # Ignore messages from bots
    if message.author.bot:
        return

    # Check for profanity
    await check_profanity(message)

    # Don't forget to process commands
    await bot.process_commands(message)

async def check_profanity(message):
    if predict([message.content])[0] == 1: 
        await message.delete()
        await message.channel.send(f"{message.author.mention}, your message contained profanity and has been deleted.")
        
        # Store the warning in the database
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        c.execute("SELECT warnings FROM warnings WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        result = c.fetchone()

        if result:
            warnings = result[0] + 1
            c.execute("UPDATE warnings SET warnings=? WHERE guild_id=? AND user_id=?", (warnings, guild_id, user_id))
        else:
            warnings = 1
            c.execute("INSERT INTO warnings (guild_id, user_id, warnings) VALUES (?, ?, ?)", (guild_id, user_id, warnings))

        conn.commit()

        if warnings >= 3:
            await message.author.ban(reason="Accumulated 3 warnings for profanity.")
            await message.channel.send(f"{message.author.mention} has been banned for accumulating 3 warnings.")
            print(f"Banned {message.author.name} from {message.guild.name} for 3 warnings.")

# Start the check_idle_users loop when the bot is ready
@bot.event
async def on_ready():
    print(f"Moderator bot logged in as {bot.user.name}")
    check_idle_users.start()  # Start the loop to check idle users

    for guild in bot.guilds:
        print(f'Connected to guild: {guild.name}')
