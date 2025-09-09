import pygame
import sys
import config
from audio import get_connected_audio_devices
from youtube import search_youtube, download_audio_worker
from player import toggle_play_pause, handle_music_end_event, play_next_song
from pygame import mixer
import threading


class MusicPlayerUI:
    def __init__(self):
        """Initialize the pygame UI"""
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption("Music Player with Discord Integration")
        self.clock = pygame.time.Clock()

        # Initialize fonts
        self.font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)

        # Audio device check timing
        self.last_audio_check = 0

        # Initialize result rectangles list
        config.result_rects = []

    def handle_events(self):
        """Handle pygame events"""

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse_click(event)

            elif event.type == config.MUSIC_END:
                handle_music_end_event()

            elif event.type == config.NEXT_SONG_EVENT:
                self._handle_next_song_event()

            elif event.type == pygame.KEYDOWN:
                self._handle_keyboard_input(event)

    def _handle_mouse_click(self, event):
        """Handle mouse click events"""

        # Search box click
        if config.SEARCH_BOX.collidepoint(event.pos):
            config.search_active = True
        else:
            config.search_active = False

        # Search result clicks
        for i, rect in enumerate(config.result_rects):
            if rect.collidepoint(event.pos) and i < len(config.search_results):
                video_info = config.search_results[i]

                this_song_gets_auto_play_chance = False
                if not config.is_playing and not mixer.music.get_busy():
                    with config.auto_play_lock:
                        if not config.is_auto_play_pending:
                            config.is_auto_play_pending = True
                            this_song_gets_auto_play_chance = True

                thread = threading.Thread(
                    target=download_audio_worker,
                    args=(video_info, this_song_gets_auto_play_chance)
                )
                thread.daemon = True
                thread.start()

                if this_song_gets_auto_play_chance:
                    print(f"Pygame: Attempting auto-play with {video_info['title']}")

        # Play/Pause button
        if config.PLAY_BUTTON.collidepoint(event.pos):
            toggle_play_pause()

        # Skip button
        if config.SKIP_BUTTON.collidepoint(event.pos):
            with config.queue_lock:
                if config.is_playing or mixer.music.get_busy():
                    mixer.music.stop()
                    pygame.time.set_timer(config.NEXT_SONG_EVENT, 10)

        # Volume slider
        if config.VOLUME_SLIDER.collidepoint(event.pos):
            config.volume_level = (event.pos[0] - config.VOLUME_SLIDER.x) / config.VOLUME_SLIDER.width
            config.volume_level = max(0, min(1, config.volume_level))
            mixer.music.set_volume(config.volume_level)

    def _handle_next_song_event(self):
        """Handle the next song event"""
        pygame.time.set_timer(config.NEXT_SONG_EVENT, 0)  # Turn off the timer

        print("Playing next song from queue...")
        if config.queued_songs:
            print(f"Queue has {len(config.queued_songs)} songs. Next up: {config.queued_songs[0]['title'] if config.queued_songs else 'None'}")

        # Only play next song if we're not already playing something
        if not config.is_playing and not mixer.music.get_busy():
            play_next_song()

    def _handle_keyboard_input(self, event):
        """Handle keyboard input events"""
        if config.search_active:
            if event.key == pygame.K_RETURN:
                config.search_results = search_youtube(config.search_text)
                config.result_rects = [pygame.Rect(50, 100 + i*40, 500, 32)
                              for i in range(len(config.search_results))]
            elif event.key == pygame.K_BACKSPACE:
                config.search_text = config.search_text[:-1]
            else:
                config.search_text += event.unicode

    def update_audio_devices(self):
        """Periodically update audio device information"""
        current_time = pygame.time.get_ticks()
        if current_time - self.last_audio_check > config.AUDIO_CHECK_INTERVAL:
            config.connected_audio_device = get_connected_audio_devices()
            self.last_audio_check = current_time

    def draw(self):
        """Draw all UI elements"""
        self.screen.fill(config.BLACK)

        self._draw_search_box()
        self._draw_search_results()
        self._draw_playback_controls()
        self._draw_volume_slider()
        self._draw_audio_status()
        self._draw_song_info()
        self._draw_discord_status()

        pygame.display.update()

    def _draw_search_box(self):
        """Draw the search input box"""
        color = config.WHITE if config.search_active else config.GRAY
        pygame.draw.rect(self.screen, color, config.SEARCH_BOX, 2)
        search_surface = self.font.render(config.search_text, True, config.WHITE)
        self.screen.blit(search_surface, (config.SEARCH_BOX.x + 5, config.SEARCH_BOX.y + 5))

    def _draw_search_results(self):
        """Draw the search results list"""
        for i, result in enumerate(config.search_results):
            result_surface = self.font.render(result['title'][:50], True, config.WHITE)
            self.screen.blit(result_surface, (50, 100 + i*40))
            if i < len(config.result_rects):
                pygame.draw.rect(self.screen, config.GRAY, config.result_rects[i], 1)

    def _draw_playback_controls(self):
        """Draw play/pause and skip buttons"""
        # Play/Pause button
        pygame.draw.rect(self.screen, config.GREEN if config.is_playing else config.WHITE, config.PLAY_BUTTON)
        play_text = self.font.render("⏸" if config.is_playing else "▶", True, config.BLACK)
        self.screen.blit(play_text, (config.PLAY_BUTTON.centerx - 10, config.PLAY_BUTTON.centery - 10))

        # Skip button
        pygame.draw.rect(self.screen, config.WHITE, config.SKIP_BUTTON)
        skip_text = self.font.render("⏭", True, config.BLACK)
        self.screen.blit(skip_text, (config.SKIP_BUTTON.centerx - 10, config.SKIP_BUTTON.centery - 10))

    def _draw_volume_slider(self):
        """Draw the volume control slider"""
        pygame.draw.rect(self.screen, config.GRAY, config.VOLUME_SLIDER)
        volume_pos = config.VOLUME_SLIDER.x + (config.VOLUME_SLIDER.width * config.volume_level)
        pygame.draw.circle(self.screen, config.WHITE, (int(volume_pos), config.VOLUME_SLIDER.centery), 8)

    def _draw_audio_status(self):
        """Draw audio device status"""
        audio_status_surface = self.small_font.render(config.connected_audio_device, True, config.WHITE)
        self.screen.blit(audio_status_surface, (config.VOLUME_SLIDER.x, config.VOLUME_SLIDER.y - 25))

    def _draw_song_info(self):
        """Draw current song and queue information"""
        # Current song
        if config.currently_playing:
            current_text = self.small_font.render(f"Now Playing: {config.currently_playing['title'][:40]}", True, config.WHITE)
            self.screen.blit(current_text, (50, 450))

        # Queue size
        queue_size = len(config.queued_songs)
        queue_text = self.small_font.render(f"Queue: {queue_size} song{'s' if queue_size != 1 else ''}", True, config.WHITE)
        self.screen.blit(queue_text, (50, 475))

    def _draw_discord_status(self):
        """Draw Discord bot status and last command"""
        # Discord status
        bot_status = self.small_font.render(config.discord_status, True, config.WHITE)
        self.screen.blit(bot_status, (50, 550))

        # Last Discord command
        if config.discord_last_command:
            cmd_text = self.small_font.render(f"Last command: {config.discord_last_command}", True, config.WHITE)
            self.screen.blit(cmd_text, (50, 575))

    def run(self):
        """Main UI loop"""
        while True:
            self.handle_events()
            self.update_audio_devices()
            self.draw()
            self.clock.tick(60)
