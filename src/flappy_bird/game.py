"""Game lifecycle: window, main loop, event handling, update and rendering."""

from __future__ import annotations

import os

import pygame

from . import settings
from .collision import check_any_pipe_collision
from .pipe import Pipe
from .pipe_manager import PipeManager
from .player import Player
from .scoring import count_newly_passed
from .utils import centered_rect, frame_delta


class Game:
    """Owns the window and drives the main loop."""

    def __init__(self, headless: bool = False) -> None:
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

        pygame.init()
        pygame.display.set_caption(settings.CAPTION)
        self.screen = pygame.display.set_mode(
            (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        )
        self.clock = pygame.time.Clock()
        self.score_font = pygame.font.Font(None, settings.SCORE_FONT_SIZE)
        self.banner_font = pygame.font.Font(None, settings.BANNER_FONT_SIZE)

        self.player = Player()
        self.pipe_manager = PipeManager()
        self.score = 0
        self.high_score = 0
        self.running = False
        self.game_over = False
        self.has_flapped = False

    @property
    def pipes(self) -> list[Pipe]:
        """Live list of active pipes, owned by the pipe manager."""
        return self.pipe_manager.pipes

    # --- Lifecycle -----------------------------------------------------------

    def run(self, max_frames: int | None = None) -> None:
        """Run the main loop until the window closes.

        ``max_frames`` stops the loop early, which keeps automated runs short.
        """
        self.running = True
        frames = 0
        while self.running:
            self.handle_events()
            self.update(frame_delta(self.clock, settings.FPS))
            self.render()
            pygame.display.flip()

            frames += 1
            if max_frames is not None and frames >= max_frames:
                self.running = False
        pygame.quit()

    def restart(self) -> None:
        self.player.reset()
        self.pipe_manager.reset()
        self.score = 0
        self.game_over = False
        self.has_flapped = False

    def add_score(self, points: int) -> None:
        """Award points to the current score and keep the high score current."""
        self.score += points
        self.high_score = max(self.high_score, self.score)

    # --- Loop stages ---------------------------------------------------------

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.flap()

    def handle_keydown(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_r:
            self.restart()
        elif key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
            self.flap()

    def flap(self) -> None:
        """Make the bird flap, unless the round is already over."""
        if self.game_over:
            return
        self.player.jump()
        self.has_flapped = True

    def update(self, dt: float) -> None:
        if self.game_over:
            return

        self.player.update(dt)
        self.pipe_manager.update(dt)

        if self.player.is_out_of_bounds or check_any_pipe_collision(
            self.player, self.pipes
        ):
            self.game_over = True
            return

        self.add_score(count_newly_passed(self.player, self.pipes))

    # --- Rendering -----------------------------------------------------------

    def render(self) -> None:
        self.screen.fill(settings.BACKGROUND_COLOR)
        for pipe in self.pipes:
            pipe.draw(self.screen)
        self.player.draw(self.screen)
        self._draw_ground()
        self._draw_score()
        if self.game_over:
            self._draw_banner("GAME OVER", "press R to restart")
        elif not self.has_flapped:
            self._draw_banner("FLAPPY BIRD", "space or click to flap")

    def _draw_ground(self) -> None:
        ground = pygame.Rect(
            0, settings.GROUND_TOP, settings.SCREEN_WIDTH, settings.GROUND_HEIGHT
        )
        pygame.draw.rect(self.screen, settings.GROUND_COLOR, ground)

    def _draw_score(self) -> None:
        label = self._render_text(f"Score: {self.score}")
        self.screen.blit(label, self._centered_x(label, settings.SCORE_TEXT_Y))
        if self.game_over:
            best = self._render_text(f"Best: {self.high_score}")
            best_y = settings.SCORE_TEXT_Y + label.get_height() + 4
            self.screen.blit(best, self._centered_x(best, best_y))

    def _render_text(self, text: str) -> pygame.Surface:
        return self.score_font.render(text, True, settings.TEXT_COLOR)

    def _centered_x(self, label: pygame.Surface, y: int) -> tuple[int, int]:
        return ((settings.SCREEN_WIDTH - label.get_width()) // 2, y)

    def _draw_banner(self, title: str, subtitle: str) -> None:
        title_label = self.banner_font.render(title, True, settings.TEXT_COLOR)
        subtitle_label = self.banner_font.render(subtitle, True, settings.TEXT_COLOR)
        banner = pygame.Surface(
            (max(title_label.get_width(), subtitle_label.get_width()) + 40, 80)
        )
        banner.set_alpha(180)
        banner.fill((255, 255, 255))

        banner.blit(title_label, centered_rect(title_label, banner.get_size()))
        banner.blit(
            subtitle_label,
            (
                (banner.get_width() - subtitle_label.get_width()) // 2,
                title_label.get_height() + 10,
            ),
        )
        self.screen.blit(banner, centered_rect(banner, self.screen.get_size()))
