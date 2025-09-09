import pygame
from pygame import mixer
from config import ensure_downloads_directory, MUSIC_END
from discord_bot import start_discord_bot
from ui import MusicPlayerUI


def main():
    """Main application entry point"""
    # Initialize pygame mixer
    mixer.init()

    # Set up custom pygame events
    pygame.mixer.music.set_endevent(MUSIC_END)

    # Ensure downloads directory exists and is clean
    ensure_downloads_directory()

    # Start Discord bot in background thread
    start_discord_bot()

    # Create and run the UI
    ui = MusicPlayerUI()
    ui.run()


if __name__ == "__main__":
    main()
