# Pygame Music Player with Discord Integration

This application combines a Pygame-based music player with Discord bot controls, allowing you to control your music player through Discord commands.

## Setup

1. Install the required dependencies:
   ```
   pip install pygame yt_dlp discord.py python-dotenv
   ```

2. Create a `.env` file in the root directory with your Discord bot token:
   ```
   DISCORD_TOKEN=your_discord_token_here
   ```

3. Run the application:
   ```
   python interface.py
   ```

## Discord Commands

- `!play [query]` - Search and play a song from YouTube
- `!pause` - Pause the current playback
- `!resume` - Resume playback if paused
- `!skip` - Skip to the next song in the queue
- `!queue` - Display the current song queue
- `!volume [level]` - Set volume (0-100)

## Pygame Interface

The Pygame interface provides local controls and shows the Discord bot status at the bottom of the screen.

- Search for songs and click on results to add them to the queue
- Use play/pause button to control playback
- Adjust volume with the slider
- Skip button to play the next song

## How It Works

The application runs both the Pygame interface and Discord bot simultaneously using threading. Commands from Discord are reflected in the local player and vice versa. 