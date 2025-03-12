import os
import discord
import yt_dlp
import asyncio
from discord.ext import commands
from discord import app_commands
from collections import deque
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Constants
PRINT_GUILD_ID = False

# Song queue
queue = {}

async def get_song_info(query, ydl_opts):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    return yt_dlp.YoutubeDL(ydl_opts).extract_info(query, download=False)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print(f'Synced slash commands for {bot.user}')
    except Exception as e:
        print(f'Error syncing commands: {e}')
    
    print(f'Logged in as {bot.user.name}')

if PRINT_GUILD_ID:
    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        else:
            print(f'{message.author.name} sent: {message.content}')
            print(message.guild.id)

@bot.tree.command(name='play', description='Play a song or add it to the queue')
@app_commands.describe(song_query="Search Query or URL")
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer()

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send('You need to be in a voice channel to use this command.')
        return

    voice_channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client

    # Ensure bot is in the correct voice channel
    if voice_client is None or not voice_client.is_connected():
        try:
            voice_client = await voice_channel.connect()
        except Exception as e:
            await interaction.followup.send(f'Error connecting to voice channel: {str(e)}')
            return
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    # YTDL options
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'youtube_include_dash_manifest': False,
        'youtube_include_hls_manifest': False,
        'noplaylist': True,
        'quiet': True,
    }

    query = f'ytsearch:{song_query}'
    results = await get_song_info(query, ydl_opts)
    tracks = results.get('entries', [])

    if not tracks:
        await interaction.followup.send('No results found.')
        return
    
    track = tracks[0]
    track_url = track['url']
    track_title = track.get('title', 'Untitled')

    guild_id = str(interaction.guild.id)
    if guild_id not in queue:
        queue[guild_id] = deque()
    
    queue[guild_id].append((track_url, track_title))

    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f'Added **{track_title}** to the queue.')
    else:
        await interaction.followup.send(f'Now playing: **{track_title}**')
        await play_next_song(voice_client, guild_id, interaction.channel, queue)

async def play_next_song(voice_client, guild_id, channel, queue):
    if guild_id not in queue or not queue[guild_id]:
        await voice_client.disconnect()
        queue[guild_id] = deque()
        return
    
    track_url, title = queue[guild_id].popleft()
    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    source = discord.FFmpegPCMAudio(track_url, **ffmpeg_options)

    def after(e):
        if e:
            print(f'Error playing {title}: {str(e)}')
        future = asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel, queue), bot.loop)
        try:
            future.result()
        except Exception as exc:
            print(f'Error in play_next_song: {exc}')
    
    if voice_client:
        voice_client.play(source, after=after)
        await channel.send(f'Now playing: **{title}**')
    else:
        await channel.send('Failed to join voice channel.')

@bot.tree.command(name='skip', description='Skip the current song')
async def skip(interaction: discord.Interaction):
    await interaction.response.defer()
    if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        interaction.guild.voice_client.stop()
        await interaction.followup.send('Skipped the current song.')
    else:
        await interaction.followup.send('No song is currently playing.')

@bot.tree.command(name='queue', description='Display the current song queue')
async def queue_command(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_id = str(interaction.guild.id)
    if guild_id not in queue or not queue[guild_id]:
        await interaction.followup.send('The queue is empty.')
        return
    queue_list = '\n'.join([f'{i+1}. {track[1]}' for i, track in enumerate(queue[guild_id])])
    await interaction.followup.send(f'**Song Queue**\n{queue_list}')

@bot.tree.command(name='stop', description='Stop the current song, clear the queue, and leave the voice channel')
async def stop(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_id = str(interaction.guild.id)

    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        interaction.guild.voice_client.disconnect()
        queue[guild_id] = deque()
        await interaction.followup.send('Stopped the current song, cleared the queue, and left the voice channel.')
    else:
        await interaction.followup.send('Not connected to a voice channel.')

if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print('Discord token not found')
