import os
import pygame
from pygame import mixer
import config


def play_next_song():
    """Play the next song in the queue"""

    # First make sure no other playback is happening
    if mixer.music.get_busy():
        mixer.music.stop()

    # Get the next song from queue with proper locking
    next_song_info = None

    with config.queue_lock:
        queue_size = len(config.queued_songs)
        print(f"Queue before play_next_song: {queue_size} songs")
        if queue_size > 0:
            print(f"First in queue: {config.queued_songs[0]['title']}")

        # We'll skip cleanup during playback to avoid file access issues
        # cleanup_songs_internal()

        # Now get the next song if available
        if config.queued_songs:
            next_song_info = config.queued_songs.pop(0)
            print(f"Popped song from queue: {next_song_info['title']}")
            print(f"Remaining queue: {len(config.queued_songs)} songs")
            if config.queued_songs:
                print(f"Next in queue will be: {config.queued_songs[0]['title']}")

    # If we got a song to play, try to play it
    if next_song_info:
        # Set playing state before actually playing to prevent race conditions
        config.current_song = next_song_info['path']
        config.currently_playing = next_song_info

        if os.path.exists(next_song_info['path']):
            try:
                mixer.music.load(next_song_info['path'])
                mixer.music.set_volume(config.volume_level)
                mixer.music.play()
                config.is_playing = True  # Only set to True if successful
                config.paused_time = 0
                print(f"Now playing: {next_song_info['title']}")
            except Exception as e:
                print(f"Error playing {next_song_info['path']}: {e}")
                # Don't call play_next_song recursively - use timer
                config.current_song = None
                config.currently_playing = None
                config.is_playing = False
                pygame.time.set_timer(config.NEXT_SONG_EVENT, 10)  # Try next song
        else:
            print(f"Error: Song file not found: {next_song_info['path']}. Skipping.")
            config.current_song = None
            config.currently_playing = None
            config.is_playing = False
            pygame.time.set_timer(config.NEXT_SONG_EVENT, 10)  # Try next song
    else:
        # No songs in queue
        print("No songs in queue to play.")
        config.currently_playing = None
        config.current_song = None
        config.is_playing = False


def cleanup_songs_internal():
    """Internal cleanup function that assumes the queue_lock is already held"""

    # Build a set of active song paths (songs in queue or currently playing)
    active_song_paths = {song['path'] for song in config.queued_songs}
    if config.currently_playing and config.currently_playing['path']:
        active_song_paths.add(config.currently_playing['path'])

    # Also consider the current_song path separately, as it might be playing
    if config.current_song:
        active_song_paths.add(config.current_song)

    # Check if mixer is busy
    mixer_busy = mixer.music.get_busy()

    songs_to_remove = []
    for song_info in config.downloaded_songs:
        # Skip current song if mixer is busy
        if mixer_busy and song_info['path'] == config.current_song:
            continue

        if song_info['path'] not in active_song_paths:
            try:
                if os.path.exists(song_info['path']):
                    # Check if file is not currently playing before deleting
                    if not (mixer_busy and song_info['path'] == config.current_song):
                        try:
                            os.remove(song_info['path'])
                        except PermissionError:
                            print(f"Skipping delete of in-use file: {song_info['path']}")
                songs_to_remove.append(song_info)
            except Exception as e:
                print(f"Error cleaning up {song_info['path']}: {e}")

    for song_info in songs_to_remove:
        if song_info in config.downloaded_songs:
            config.downloaded_songs.remove(song_info)


def cleanup_songs():
    """Clean up downloaded songs that are no longer needed"""
    with config.queue_lock:
        cleanup_songs_internal()


def toggle_play_pause():
    """Toggle between play and pause states"""

    if config.is_playing:
        mixer.music.pause()
        config.is_playing = False
        config.paused_time = mixer.music.get_pos()
    else:
        if config.current_song:  # If there's a song loaded (paused or previously played)
            if config.paused_time > 0:  # Resuming a paused song
                mixer.music.unpause()
            else:  # Starting a song from the beginning
                if os.path.exists(config.current_song):
                    mixer.music.play()
                else:
                    print(f"Error: Song file not found: {config.current_song}")
                    return
        else:
            # No current song, try to play the next one in queue
            if config.queued_songs:
                pygame.time.set_timer(config.NEXT_SONG_EVENT, 10)
                return
            else:
                print("No songs to play")
                return
        config.is_playing = True


def handle_music_end_event():
    """Handle when a song finishes playing naturally"""

    # Set is_playing to False to indicate we're ready for the next song
    config.is_playing = False

    with config.queue_lock:
        if config.queued_songs:  # If there are more songs in the queue
            # Schedule next song to play on main thread
            pygame.time.set_timer(config.NEXT_SONG_EVENT, 10)  # Small delay
        else:
            print("Queue is empty. Playback stopped.")
