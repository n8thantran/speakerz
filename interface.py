import pygame
import sys
import yt_dlp
from pygame import mixer
import threading
from queue import Queue
import os
import discord
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import platform
import subprocess
import sounddevice as sd

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

pygame.init()
mixer.init()

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
GREEN = (0, 255, 0)

screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Music Player with Discord Integration")
clock = pygame.time.Clock()

# Font
font = pygame.font.Font(None, 32)
small_font = pygame.font.Font(None, 24)

# Search box
search_box = pygame.Rect(50, 50, 500, 32)
search_text = ""
search_active = False

# Music controls
play_button = pygame.Rect(50, 500, 80, 32)
skip_button = pygame.Rect(140, 500, 80, 32)
volume_slider = pygame.Rect(300, 500, 200, 10)
volume_level = 0.7  # 50% volume (renamed from volume to avoid conflict)
is_playing = False
current_song = None
current_pos = 0.0  # Track the current position in seconds
paused_time = 0   # Store when we paused
discord_status = "Discord bot: Disconnected"
discord_last_command = ""

# Audio device monitoring
connected_audio_device = "Audio: No devices found"
last_audio_check = 0
AUDIO_CHECK_INTERVAL = 5000  # Check every 5 seconds (in milliseconds)

# Search results
search_results = []
result_rects = []
downloaded_songs = []
currently_playing = None  # Track currently playing song info
queued_songs = []  # List to maintain order of songs

# Auto-play synchronization
auto_play_lock = threading.Lock()
is_auto_play_pending = False # True if a song is currently tasked with initiating auto-play
queue_lock = threading.Lock() # Lock for thread-safe queue operations

# Create downloads directory if it doesn't exist
if not os.path.exists('downloads'):
    os.makedirs('downloads')
else:
    # Clear the downloads folder on startup
    for filename in os.listdir('downloads'):
        file_path = os.path.join('downloads', filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path): # If there are subdirectories for some reason
                # shutil.rmtree(file_path) # Requires import shutil
                # For simplicity, we'll just print a warning if we find a dir,
                # as the primary goal is to clear downloaded song files.
                print(f"Warning: Subdirectory found in downloads: {file_path}. Manual cleanup might be needed.")
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')

# Discord bot setup
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
bot_ready = False

def sanitize_filename(title):
    """Make filename safe for Windows file system"""
    # Replace problematic characters
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in invalid_chars:
        title = title.replace(char, '_')
    return title

def get_connected_audio_devices():
    """Get the name of the default audio output device using sounddevice."""
    try:
        device_info = sd.query_devices(kind='output')
        if not device_info:
            return "Audio: No default output device found"
        
        device_name = device_info.get('name', 'Unknown Device')
        
        # Check for bluetooth keywords and add an icon
        is_bluetooth = any(keyword in device_name.lower() for keyword in ['bluetooth', 'bt', 'wireless', 'airpods', 'headset', 'soundcore'])
        
        prefix = "🔵 " if is_bluetooth else ""
        return f"Audio: {prefix}{device_name}"
            
    except Exception as e:
        print(f"Error getting audio device: {e}")
        return "Audio: Error detecting device"

def search_youtube(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        results = ydl.extract_info(f"ytsearch5:{query}", download=False)
        return results.get('entries', [])

def download_audio_worker(video_info, has_auto_play_chance):
    global is_playing, mixer, current_song, currently_playing, paused_time
    global queued_songs, downloaded_songs
    global is_auto_play_pending, auto_play_lock, queue_lock

    # Create sanitized filename based on title
    original_title = video_info['title']
    sanitized_title = sanitize_filename(original_title)
    song_path = f"downloads/{sanitized_title}.mp3"
    
    # Use consistent quiet and no_warnings options
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': f'downloads/{sanitized_title}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    
    download_succeeded = False
    downloaded_song_info = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_info['url']])
        
        # Verify file exists after download
        if os.path.exists(song_path):
            downloaded_song_info = {'title': original_title, 'path': song_path}
            
            # Thread-safe queue modifications with lock
            with queue_lock:
                queued_songs.append(downloaded_song_info)
                downloaded_songs.append(downloaded_song_info)
                download_succeeded = True
                print(f"Added to queue: {original_title}")
                print(f"Queue now has {len(queued_songs)} songs")
        else:
            print(f"Error: File not found after download: {song_path}")
            download_succeeded = False

    except yt_dlp.utils.DownloadError as de:
        print(f"yt-dlp DownloadError for '{original_title}': {de}")
    except Exception as e:
        print(f"Error downloading '{original_title}': {e}")
    
    if not download_succeeded:
        if has_auto_play_chance:
            with auto_play_lock:
                is_auto_play_pending = False
        return

    # Download succeeded and song is queued
    if has_auto_play_chance:
        should_actually_play_now = False
        with auto_play_lock:
            if is_auto_play_pending and not is_playing and not mixer.music.get_busy():
                with queue_lock:
                    if queued_songs and queued_songs[0]['path'] == downloaded_song_info['path']:
                        should_actually_play_now = True
            
            is_auto_play_pending = False 

        if should_actually_play_now:
            pygame.time.set_timer(NEXT_SONG_EVENT, 10)  # Schedule play_next_song instead of calling directly

def play_next_song():
    global current_song, is_playing, paused_time, currently_playing, queued_songs
    
    # First make sure no other playback is happening
    if mixer.music.get_busy():
        mixer.music.stop()
    
    # Get the next song from queue with proper locking
    next_song_info = None
    
    with queue_lock:
        queue_size = len(queued_songs)
        print(f"Queue before play_next_song: {queue_size} songs")
        if queue_size > 0:
            print(f"First in queue: {queued_songs[0]['title']}")
        
        # We'll skip cleanup during playback to avoid file access issues
        # cleanup_songs_internal()
        
        # Now get the next song if available
        if queued_songs:
            next_song_info = queued_songs.pop(0)
            print(f"Popped song from queue: {next_song_info['title']}")
            print(f"Remaining queue: {len(queued_songs)} songs")
            if queued_songs:
                print(f"Next in queue will be: {queued_songs[0]['title']}")
    
    # If we got a song to play, try to play it
    if next_song_info:
        # Set playing state before actually playing to prevent race conditions
        current_song = next_song_info['path']
        currently_playing = next_song_info
        
        if os.path.exists(next_song_info['path']):
            try:
                mixer.music.load(next_song_info['path'])
                mixer.music.set_volume(volume_level)
                mixer.music.play()
                is_playing = True  # Only set to True if successful
                paused_time = 0
                print(f"Now playing: {next_song_info['title']}")
            except Exception as e:
                print(f"Error playing {next_song_info['path']}: {e}")
                # Don't call play_next_song recursively - use timer
                current_song = None
                currently_playing = None
                is_playing = False
                pygame.time.set_timer(NEXT_SONG_EVENT, 10)  # Try next song
        else:
            print(f"Error: Song file not found: {next_song_info['path']}. Skipping.")
            current_song = None
            currently_playing = None
            is_playing = False
            pygame.time.set_timer(NEXT_SONG_EVENT, 10)  # Try next song
    else:
        # No songs in queue
        print("No songs in queue to play.")
        currently_playing = None
        current_song = None
        is_playing = False

# Internal cleanup function that assumes the queue_lock is already held
def cleanup_songs_internal():
    global downloaded_songs, queued_songs, currently_playing, current_song
    
    # Build a set of active song paths (songs in queue or currently playing)
    active_song_paths = {song['path'] for song in queued_songs}
    if currently_playing and currently_playing['path']:
        active_song_paths.add(currently_playing['path'])
    
    # Also consider the current_song path separately, as it might be playing
    if current_song:
        active_song_paths.add(current_song)
    
    # Check if mixer is busy
    mixer_busy = mixer.music.get_busy()
    
    songs_to_remove = []
    for song_info in downloaded_songs:
        # Skip current song if mixer is busy
        if mixer_busy and song_info['path'] == current_song:
            continue
            
        if song_info['path'] not in active_song_paths:
            try:
                if os.path.exists(song_info['path']):
                    # Check if file is not currently playing before deleting
                    if not (mixer_busy and song_info['path'] == current_song):
                        try:
                            os.remove(song_info['path'])
                        except PermissionError:
                            print(f"Skipping delete of in-use file: {song_info['path']}")
                songs_to_remove.append(song_info)
            except Exception as e:
                print(f"Error cleaning up {song_info['path']}: {e}")
    
    for song_info in songs_to_remove:
        if song_info in downloaded_songs:
            downloaded_songs.remove(song_info)

# Original cleanup function that acquires the lock first
def cleanup_songs():
    with queue_lock:
        cleanup_songs_internal()

def toggle_play_pause():
    global is_playing, paused_time, current_song
    
    if is_playing:  
        mixer.music.pause()
        is_playing = False
        paused_time = mixer.music.get_pos()  
    else:
        if current_song: # If there's a song loaded (paused or previously played)
            if paused_time > 0: # Resuming a paused song
                mixer.music.unpause()
            else: # Starting a new song or restarting current_song if it ended and wasn't cleared
                mixer.music.load(current_song)
                mixer.music.play() # Start from beginning
            mixer.music.set_volume(volume_level) # Apply volume
            is_playing = True
        elif queued_songs: # Nothing loaded/paused, but queue has songs
            play_next_song()
            # paused_time should be 0 as a new song starts

# Ensure the MUSIC_END event handler also uses proper locking
def handle_music_end_event():
    # This is called when a song finishes playing naturally
    global is_playing
    
    # Set is_playing to False to indicate we're ready for the next song
    is_playing = False
    
    with queue_lock:
        if queued_songs:  # If there are more songs in the queue
            # Schedule next song to play on main thread
            pygame.time.set_timer(NEXT_SONG_EVENT, 10)  # Small delay

# Create a custom event for handling song end
MUSIC_END = pygame.USEREVENT + 1
NEXT_SONG_EVENT = pygame.USEREVENT + 2
mixer.music.set_endevent(MUSIC_END)

@bot.event
async def on_ready():
    global bot_ready, discord_status
    print(f'Discord bot connected as {bot.user}')
    bot_ready = True
    discord_status = f"Discord bot: Connected as {bot.user.name}"
    await bot.change_presence(activity=discord.Game(name="!help for commands"))

@bot.command()
async def play(ctx, *, query):
    """Play a song from YouTube"""
    global discord_last_command, is_auto_play_pending, auto_play_lock, is_playing
    discord_last_command = f"!play {query}"
    
    results = search_youtube(query)
    if not results:
        embed = discord.Embed(
            title="❌ No Results Found",
            description="No results found for your query.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
        
    video_info = results[0]
    embed = discord.Embed(
        title="🎵 Added to Queue",
        description=f"{video_info['title']}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)
    
    this_song_gets_auto_play_chance = False
    if not is_playing and not mixer.music.get_busy(): 
        with auto_play_lock:
            if not is_auto_play_pending:
                is_auto_play_pending = True
                this_song_gets_auto_play_chance = True
    
    thread = threading.Thread(
        target=download_audio_worker,
        args=(video_info, this_song_gets_auto_play_chance)
    )
    thread.daemon = True
    thread.start()
    
    if this_song_gets_auto_play_chance:
        embed = discord.Embed(
            title="▶️ Starting Playback",
            description=f"Attempting to start playback with: {video_info['title']}",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

@bot.command()
async def pause(ctx):
    """Pause the current song"""
    global is_playing, discord_last_command
    
    if is_playing:
        toggle_play_pause()
        embed = discord.Embed(
            title="⏸️ Playback Paused",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        discord_last_command = "!pause"
    else:
        embed = discord.Embed(
            title="❌ Nothing Playing",
            description="Nothing is currently playing.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command()
async def resume(ctx):
    """Resume playback"""
    global is_playing, discord_last_command
    
    if not is_playing and current_song:
        toggle_play_pause()
        embed = discord.Embed(
            title="▶️ Playback Resumed",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        discord_last_command = "!resume"
    else:
        embed = discord.Embed(
            title="❌ Not Paused",
            description="Nothing is paused.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command()
async def skip(ctx):
    """Skip to the next song"""
    global is_playing, discord_last_command, queue_lock
    
    skipped = False
    with queue_lock:
        if is_playing or mixer.music.get_busy():
            mixer.music.stop()
            skipped = True
            pygame.time.set_timer(NEXT_SONG_EVENT, 10)
    
    if skipped:
        embed = discord.Embed(
            title="⏭️ Skipped to Next Song",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        discord_last_command = "!skip"
    else:
        embed = discord.Embed(
            title="❌ Nothing Playing",
            description="Nothing is currently playing.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command()
async def queue(ctx):
    """Show the current queue"""
    embed = discord.Embed(
        title="🎵 Music Queue",
        color=discord.Color.blue()
    )
    
    # Lock the queue while reading it
    with queue_lock:
        if currently_playing:
            embed.add_field(
                name="🔊 Now Playing",
                value=currently_playing['title'],
                inline=False
            )
        
        if queued_songs:
            queue_text = ""
            for i, song in enumerate(queued_songs, 1):
                queue_text += f"{i}. {song['title']}\n"
            
            embed.add_field(
                name="📋 Up Next",
                value=queue_text,
                inline=False
            )
        
        if not currently_playing and not queued_songs:
            embed.description = "Queue is empty. Add songs with !play"
    
    await ctx.send(embed=embed)

@bot.command()
async def volume(ctx, level: int):
    """Set volume (0-100)"""
    global volume_level, discord_last_command
    
    new_level = max(0, min(100, level)) / 100.0
    volume_level = new_level
    mixer.music.set_volume(volume_level)
    
    embed = discord.Embed(
        title="🔊 Volume Changed",
        description=f"Volume set to {int(volume_level*100)}%",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)
    discord_last_command = f"!volume {level}"

def run_discord_bot():
    if DISCORD_TOKEN:
        try:
            bot.run(DISCORD_TOKEN)
        except Exception as e:
            print(f"Discord bot error: {str(e)}")
            global discord_status
            discord_status = f"Discord bot: Error - {str(e)[:30]}"
    else:
        print("Error: No Discord token found. Set DISCORD_TOKEN in .env file.")

if DISCORD_TOKEN:
    bot_thread = threading.Thread(target=run_discord_bot)
    bot_thread.daemon = True
    bot_thread.start()
else:
    discord_status = "Discord bot: No token found"

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
            
        if event.type == pygame.MOUSEBUTTONDOWN:
            if search_box.collidepoint(event.pos):
                search_active = True
            else:
                search_active = False
                
            for i, rect in enumerate(result_rects):
                if rect.collidepoint(event.pos) and i < len(search_results):
                    video_info_pygame = search_results[i] # This is the video_info from search
                    
                    this_song_gets_auto_play_chance_pygame = False
                    if not is_playing and not mixer.music.get_busy():
                        with auto_play_lock:
                            if not is_auto_play_pending:
                                is_auto_play_pending = True
                                this_song_gets_auto_play_chance_pygame = True
                    
                    thread = threading.Thread(
                        target=download_audio_worker, 
                        args=(video_info_pygame, this_song_gets_auto_play_chance_pygame)
                    )
                    thread.daemon = True
                    thread.start()
                    
                    # Optional: feedback in Pygame UI if auto-play is attempted
                    if this_song_gets_auto_play_chance_pygame:
                        print(f"Pygame: Attempting auto-play with {video_info_pygame['title']}")

            # Play/Pause button
            if play_button.collidepoint(event.pos):
                toggle_play_pause()
                
            # Skip button
            if skip_button.collidepoint(event.pos):
                # Properly handle skip with queue lock
                with queue_lock:
                    # If currently playing a song, stop it and play the next one
                    if is_playing or mixer.music.get_busy():
                        mixer.music.stop()
                        # Don't call play_next_song() directly while holding the lock
                        # Schedule it to run immediately after releasing the lock
                        pygame.time.set_timer(NEXT_SONG_EVENT, 10)  # Small delay to run on main thread
                
            # Volume slider
            if volume_slider.collidepoint(event.pos):
                volume_level = (event.pos[0] - volume_slider.x) / volume_slider.width
                volume_level = max(0, min(1, volume_level))
                mixer.music.set_volume(volume_level)
                
        if event.type == MUSIC_END:
            handle_music_end_event()
            
        if event.type == NEXT_SONG_EVENT:
            # This is called when it's time to play the next song
            # It's running on the main thread after events that might have triggered it
            pygame.time.set_timer(NEXT_SONG_EVENT, 0)  # Turn off the timer
            
            # Add debug print to track song transitions
            print("Playing next song from queue...")
            if queued_songs:
                print(f"Queue has {len(queued_songs)} songs. Next up: {queued_songs[0]['title'] if queued_songs else 'None'}")
            
            # Only play next song if we're not already playing something
            # This prevents multiple skips from occurring
            if not is_playing and not mixer.music.get_busy():
                play_next_song()
                    
        if event.type == pygame.KEYDOWN:
            if search_active:
                if event.key == pygame.K_RETURN:
                    search_results = search_youtube(search_text)
                    result_rects = [pygame.Rect(50, 100 + i*40, 500, 32) 
                                  for i in range(len(search_results))]
                elif event.key == pygame.K_BACKSPACE:
                    search_text = search_text[:-1]
                else:
                    search_text += event.unicode

    # Check audio devices periodically
    current_time = pygame.time.get_ticks()
    if current_time - last_audio_check > AUDIO_CHECK_INTERVAL:
        connected_audio_device = get_connected_audio_devices()
        last_audio_check = current_time

    screen.fill(BLACK)
    
    # Draw search box
    pygame.draw.rect(screen, WHITE if search_active else GRAY, search_box, 2)
    search_surface = font.render(search_text, True, WHITE)
    screen.blit(search_surface, (search_box.x + 5, search_box.y + 5))

    # Draw search results
    for i, result in enumerate(search_results):
        result_surface = font.render(result['title'][:50], True, WHITE)
        screen.blit(result_surface, (50, 100 + i*40))
        pygame.draw.rect(screen, GRAY, result_rects[i], 1)

    # Draw playback controls
    pygame.draw.rect(screen, GREEN if is_playing else WHITE, play_button)
    play_text = font.render("⏸" if is_playing else "▶", True, BLACK)
    screen.blit(play_text, (play_button.centerx - 10, play_button.centery - 10))

    pygame.draw.rect(screen, WHITE, skip_button)
    skip_text = font.render("⏭", True, BLACK)
    screen.blit(skip_text, (skip_button.centerx - 10, skip_button.centery - 10))

    # Draw audio device status
    audio_status_surface = small_font.render(connected_audio_device, True, WHITE)
    screen.blit(audio_status_surface, (volume_slider.x, volume_slider.y - 25))

    # Draw volume slider
    pygame.draw.rect(screen, GRAY, volume_slider)
    volume_pos = volume_slider.x + (volume_slider.width * volume_level)
    pygame.draw.circle(screen, WHITE, (int(volume_pos), volume_slider.centery), 8)
    
    # Draw current song and queue info
    if currently_playing:
        current_text = small_font.render(f"Now Playing: {currently_playing['title'][:40]}", True, WHITE)
        screen.blit(current_text, (50, 450))

    queue_size = len(queued_songs)
    queue_text = small_font.render(f"Queue: {queue_size} song{'s' if queue_size != 1 else ''}", True, WHITE)
    screen.blit(queue_text, (50, 475))
    
    # Draw Discord status
    bot_status = small_font.render(discord_status, True, WHITE)
    screen.blit(bot_status, (50, 550))
    
    # Show last Discord command if any
    if discord_last_command:
        cmd_text = small_font.render(f"Last command: {discord_last_command}", True, WHITE)
        screen.blit(cmd_text, (50, 575))
    
    pygame.display.update()
    clock.tick(60)
