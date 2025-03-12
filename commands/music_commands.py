import discord
import yt_dlp
import asyncio
from collections import deque

class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
    
    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = deque()
        return self.queues[guild_id]
    
    async def play_next(self, voice_client, guild_id, channel):
        queue = self.get_queue(guild_id)
        if not queue:
            await voice_client.disconnect()
            return
        
        track_url, title = queue.popleft()
        ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
        source = discord.FFmpegPCMAudio(track_url, **ffmpeg_options)
        
        def after(e):
            asyncio.run_coroutine_threadsafe(self.play_next(voice_client, guild_id, channel), self.bot.loop)
        
        voice_client.play(source, after=after)
        await channel.send(f'Now playing: **{title}**')

music_player = None

def register_commands(bot):
    global music_player
    music_player = MusicPlayer(bot)

    @bot.tree.command(name='play', description='Play a song or add it to the queue')
    async def play(interaction: discord.Interaction, song_query: str):
        await interaction.response.defer()
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send('You need to be in a voice channel to use this command.')
            return
        
        voice_channel = interaction.user.voice.channel
        voice_client = interaction.guild.voice_client

        if voice_client is None:
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
        
        ydl_opts = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True}
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(f'ytsearch:{song_query}', download=False))
        
        if 'entries' not in result or not result['entries']:
            await interaction.followup.send('No results found.')
            return
        
        track = result['entries'][0]
        track_url = track['url']
        track_title = track.get('title', 'Untitled')
        
        guild_id = str(interaction.guild.id)
        queue = music_player.get_queue(guild_id)
        queue.append((track_url, track_title))
        
        if not voice_client.is_playing():
            await music_player.play_next(voice_client, guild_id, interaction.channel)
        
        await interaction.followup.send(f'Added **{track_title}** to the queue.')

    @bot.tree.command(name='skip', description='Skip the current song')
    async def skip(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message('There is no music playing.')
            return

        voice_client.stop()
        await interaction.response.send_message('Skipped the current song.')

    @bot.tree.command(name='pause', description='Pause the current song')
    async def pause(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message('There is no music playing.')
            return

        voice_client.pause()
        await interaction.response.send_message('Paused the current song.')

    @bot.tree.command(name='resume', description='Resume the paused song')
    async def resume(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_paused():
            await interaction.response.send_message('There is no paused song.')
            return

        voice_client.resume()
        await interaction.response.send_message('Resumed the song.')

    @bot.tree.command(name='queue', description='View the current song queue')
    async def queue(interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        queue = music_player.get_queue(guild_id)

        if not queue:
            await interaction.response.send_message('The queue is empty.')
            return

        queue_list = '\n'.join([f'**{track[1]}**' for track in queue])
        await interaction.response.send_message(f'Current queue:\n{queue_list}')

    @bot.tree.command(name='stop', description='Stop the current song and clear the queue')
    async def stop(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message('There is no music playing.')
            return

        voice_client.stop()
        guild_id = str(interaction.guild.id)
        music_player.get_queue(guild_id).clear()
        await interaction.response.send_message('Stopped the music and cleared the queue.')