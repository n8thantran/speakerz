import os
import pygame
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize pygame
pygame.init()

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
GREEN = (0, 255, 0)

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Audio device monitoring
AUDIO_CHECK_INTERVAL = 5000  # Check every 5 seconds (in milliseconds)

# Custom pygame events
MUSIC_END = pygame.USEREVENT + 1
NEXT_SONG_EVENT = pygame.USEREVENT + 2

# Global state variables
volume_level = 0.7  # 70% volume
is_playing = False
current_song = None
current_pos = 0.0  # Track the current position in seconds
paused_time = 0   # Store when we paused
discord_status = "Discord bot: Disconnected"
discord_last_command = ""

# Audio device monitoring
connected_audio_device = "Audio: No devices found"
last_audio_check = 0

# Search and UI state
search_text = ""
search_active = False
search_results = []
result_rects = []

# Music queue and playback
downloaded_songs = []
currently_playing = None  # Track currently playing song info
queued_songs = []  # List to maintain order of songs

# Auto-play synchronization
auto_play_lock = threading.Lock()
is_auto_play_pending = False # True if a song is currently tasked with initiating auto-play
queue_lock = threading.Lock() # Lock for thread-safe queue operations

# Discord bot state
bot_ready = False

# UI element positions and sizes
SEARCH_BOX = pygame.Rect(50, 50, 500, 32)
PLAY_BUTTON = pygame.Rect(50, 500, 80, 32)
SKIP_BUTTON = pygame.Rect(140, 500, 80, 32)
VOLUME_SLIDER = pygame.Rect(300, 500, 200, 10)

# Downloads directory
DOWNLOADS_DIR = 'downloads'

def ensure_downloads_directory():
    """Create downloads directory if it doesn't exist and clear it on startup"""
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)
    else:
        # Clear the downloads folder on startup
        for filename in os.listdir(DOWNLOADS_DIR):
            file_path = os.path.join(DOWNLOADS_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    print(f"Warning: Subdirectory found in downloads: {file_path}. Manual cleanup might be needed.")
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')
