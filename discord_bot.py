import discord
from discord.ext import commands

import threading
import pygame
from pygame import mixer
import config
from youtube import search_youtube, download_audio_worker


# Discord bot setup
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())


@bot.event
async def on_ready():
    """Called when the bot is ready"""
    print(f'Discord bot connected as {bot.user}')
    config.bot_ready = True
    config.discord_status = f"Discord bot: Connected as {bot.user.name}"
    await bot.change_presence(activity=discord.Game(name="!help for commands"))


@bot.command()
async def play(ctx, *, query):
    """Play a song from YouTube"""
    config.discord_last_command = f"!play {query}"

    results = search_youtube(query)
    if not results:
        embed = discord.Embed(
            title="❌ No Results Found",
            description="No results found for your query.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Get the first result
    video_info = results[0]

    # Check if this download should get auto-play chance
    this_song_gets_auto_play_chance = False
    if not config.is_playing and not mixer.music.get_busy():
        with config.auto_play_lock:
            if not config.is_auto_play_pending:
                config.is_auto_play_pending = True
                this_song_gets_auto_play_chance = True

    # Start download in a separate thread
    thread = threading.Thread(
        target=download_audio_worker,
        args=(video_info, this_song_gets_auto_play_chance)
    )
    thread.daemon = True
    thread.start()

    embed = discord.Embed(
        title="🎵 Song Added to Queue",
        description=f"**{video_info['title']}**",
        color=discord.Color.green()
    )

    if this_song_gets_auto_play_chance:
        embed.add_field(name="Status", value="Will play immediately", inline=False)
    else:
        embed.add_field(name="Status", value="Added to queue", inline=False)

    await ctx.send(embed=embed)


@bot.command()
async def pause(ctx):
    """Pause the current song"""

    if config.is_playing:
        from player import toggle_play_pause
        toggle_play_pause()
        embed = discord.Embed(
            title="⏸️ Playback Paused",
            color=discord.Color.blue()
        )
        config.discord_last_command = "!pause"
    else:
        embed = discord.Embed(
            title="❌ Nothing is Playing",
            description="No song is currently playing.",
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)


@bot.command()
async def resume(ctx):
    """Resume playback"""

    if not config.is_playing and config.current_song:
        from player import toggle_play_pause
        toggle_play_pause()
        embed = discord.Embed(
            title="▶️ Playback Resumed",
            color=discord.Color.green()
        )
        config.discord_last_command = "!resume"
    else:
        embed = discord.Embed(
            title="❌ Nothing to Resume",
            description="No paused song found.",
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)


@bot.command()
async def skip(ctx):
    """Skip to the next song"""

    skipped = False
    with config.queue_lock:
        if config.is_playing or mixer.music.get_busy():
            mixer.music.stop()
            skipped = True
            pygame.time.set_timer(config.NEXT_SONG_EVENT, 10)

    if skipped:
        embed = discord.Embed(
            title="⏭️ Song Skipped",
            color=discord.Color.blue()
        )
        config.discord_last_command = "!skip"
    else:
        embed = discord.Embed(
            title="❌ Nothing to Skip",
            description="No song is currently playing.",
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
    with config.queue_lock:
        if config.currently_playing:
            embed.add_field(
                name="🎶 Now Playing",
                value=config.currently_playing['title'],
                inline=False
            )

        if config.queued_songs:
            queue_list = []
            for i, song in enumerate(config.queued_songs[:10], 1):  # Show first 10 songs
                queue_list.append(f"{i}. {song['title']}")

            embed.add_field(
                name=f"📋 Up Next ({len(config.queued_songs)} songs)",
                value="\n".join(queue_list) if queue_list else "Queue is empty",
                inline=False
            )

            if len(config.queued_songs) > 10:
                embed.add_field(
                    name="...",
                    value=f"And {len(config.queued_songs) - 10} more songs",
                    inline=False
                )
        else:
            embed.add_field(name="📋 Queue", value="Queue is empty", inline=False)

    await ctx.send(embed=embed)


@bot.command()
async def volume(ctx, level: int):
    """Set volume (0-100)"""

    new_level = max(0, min(100, level)) / 100.0
    config.volume_level = new_level
    mixer.music.set_volume(config.volume_level)

    embed = discord.Embed(
        title="🔊 Volume Changed",
        description=f"Volume set to {level}%",
        color=discord.Color.green()
    )
    config.discord_last_command = f"!volume {level}"
    await ctx.send(embed=embed)


def run_discord_bot():
    """Run the Discord bot in a separate thread"""
    if config.DISCORD_TOKEN:
        try:
            bot.run(config.DISCORD_TOKEN)
        except Exception as e:
            print(f"Discord bot error: {str(e)}")
            config.discord_status = f"Discord bot: Error - {str(e)[:30]}"
    else:
        print("Error: No Discord token found. Set DISCORD_TOKEN in .env file.")


def start_discord_bot():
    """Start the Discord bot in a daemon thread"""

    if config.DISCORD_TOKEN:
        bot_thread = threading.Thread(target=run_discord_bot)
        bot_thread.daemon = True
        bot_thread.start()
    else:
        config.discord_status = "Discord bot: No token found"
