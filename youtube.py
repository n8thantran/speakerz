import yt_dlp
import os

import pygame
from audio import sanitize_filename
import config
from pygame import mixer


def search_youtube(query):
    """Search YouTube for videos matching the query"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'cookiefile': 'cookies.txt',  # Use the cookies.txt file
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        results = ydl.extract_info(f"ytsearch5:{query}", download=False)
        return results.get('entries', [])


def download_audio_worker(video_info, has_auto_play_chance):
    """Download audio from YouTube video and add to queue"""

    # Create sanitized filename based on title
    original_title = video_info['title']
    sanitized_title = sanitize_filename(original_title)
    song_path = f"{config.DOWNLOADS_DIR}/{sanitized_title}.mp3"

    # Use consistent quiet and no_warnings options
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': f'{config.DOWNLOADS_DIR}/{sanitized_title}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt',  # Use the cookies.txt file
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
            with config.queue_lock:
                config.queued_songs.append(downloaded_song_info)
                config.downloaded_songs.append(downloaded_song_info)
                download_succeeded = True
                print(f"Added to queue: {original_title}")
                print(f"Queue now has {len(config.queued_songs)} songs")
        else:
            print(f"Error: File not found after download: {song_path}")
            download_succeeded = False

    except yt_dlp.utils.DownloadError as de:
        print(f"yt-dlp DownloadError for '{original_title}': {de}")
    except Exception as e:
        print(f"Error downloading '{original_title}': {e}")

    if not download_succeeded:
        if has_auto_play_chance:
            with config.auto_play_lock:
                config.is_auto_play_pending = False
        return

    # Download succeeded and song is queued
    if has_auto_play_chance:
        should_actually_play_now = False
        with config.auto_play_lock:
            if config.is_auto_play_pending and not config.is_playing and not mixer.music.get_busy():
                with config.queue_lock:
                    if config.queued_songs and downloaded_song_info and config.queued_songs[0]['path'] == downloaded_song_info['path']:
                        should_actually_play_now = True

            config.is_auto_play_pending = False

        if should_actually_play_now:
            pygame.time.set_timer(config.NEXT_SONG_EVENT, 10)  # Schedule play_next_song instead of calling directly
