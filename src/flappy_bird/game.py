"""Game lifecycle: window, states, main loop, input, update and rendering."""

from __future__ import annotations

import os

import pygame

from . import settings
from .collision import check_any_pipe_collision
from .pipe import Pipe
from .pipe_manager import PipeManager
from .player import Player
from .scoring import count_newly_passed
from .state import GameState
from .utils import centered_rect, frame_delta

#: Keys that mean "confirm" in every state: start, flap, restart.
FLAP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)


class Game:
    """Owns the window and drives the main loop.

    The lifecycle is a small state machine (see :class:`GameState`):

    ============  ==========================  ==========================
    From          Input                       Result
    ============  ==========================  ==========================
    ``START``     space / up / W / left click  ``PLAYING``
    ``PLAYING``   space / up / W / left click  flap the bird
    ``PLAYING``   collision or boundary        ``GAME_OVER``
    ``GAME_OVER`` space / up / W / left click  ``PLAYING`` (score reset)
    ============  ==========================  ==========================

    Escape quits from any state. Only ``PLAYING`` advances the simulation, so
    the attract screen and the game-over screen are both frozen worlds.
    """

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
        self.state = GameState.START
        self.score = 0
        self.high_score = 0
        self.running = False
        # Set once the player has given input this round; the START state is
        # what drives the prompt on screen, so this is only for introspection.
        self.has_flapped = False

    @property
    def pipes(self) -> list[Pipe]:
        """Live list of active pipes, owned by the pipe manager."""
        return self.pipe_manager.pipes

    @property
    def game_over(self) -> bool:
        """Backwards-compatible view of :attr:`state`."""
        return self.state is GameState.GAME_OVER

    @game_over.setter
    def game_over(self, value: bool) -> None:
        """Latch or clear the round; clearing it returns to a live round."""
        if value:
            self.state = GameState.GAME_OVER
        elif self.state is GameState.GAME_OVER:
            self.state = GameState.PLAYING

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

    def reset_round(self) -> None:
        """Clear everything that belongs to a single round and start playing.

        Resets the player, drops the pipes, restarts the spawn timer, zeroes the
        score and drops the per-pipe scoring flags along with the pipes that
        carried them. ``high_score`` is deliberately left alone.
        """
        self.player.reset()
        self.pipe_manager.reset()
        self.score = 0
        self.has_flapped = False
        self.state = GameState.PLAYING

    def start_round(self) -> None:
        """Enter ``PLAYING`` with a clean slate, from ``START`` or ``GAME_OVER``."""
        self.reset_round()

    def restart(self) -> None:
        """Alias for :meth:`start_round`, kept for the ``R`` key."""
        self.start_round()

    def add_score(self, points: int) -> None:
        """Award points to the current score and keep the high score current."""
        self.score += points
        self.high_score = max(self.high_score, self.score)

    # --- Input ----------------------------------------------------------------

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_mouse_down(event.button)

    def handle_keydown(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key in FLAP_KEYS:
            self.handle_action()
        elif key == pygame.K_r:
            self.restart()

    def handle_mouse_down(self, button: int) -> None:
        """Left click acts; right and middle clicks are ignored."""
        if button == 1:
            self.handle_action()

    def handle_action(self) -> None:
        """Act on a flap press according to the current state.

        Any state other than ``PLAYING`` first starts a fresh round, so the same
        press both starts/restarts the game and lifts the bird; the player never
        has to click twice to get off the ground.
        """
        if self.state is not GameState.PLAYING:
            self.start_round()
        self.flap()

    def flap(self) -> None:
        """Make the bird flap; ignored unless a round is being played."""
        if self.state is not GameState.PLAYING:
            return
        self.player.jump()
        self.has_flapped = True

    # --- Loop stages ---------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the simulation by ``dt`` seconds while playing.

        The attract screen and the game-over screen are frozen: no physics, no
        pipes, no scoring.
        """
        if not self.state.is_playing:
            return

        self.player.update(dt)
        self.pipe_manager.update(dt)

        if self.player.is_out_of_bounds or check_any_pipe_collision(
            self.player, self.pipes
        ):
            self.state = GameState.GAME_OVER
            return

        self.add_score(count_newly_passed(self.player, self.pipes))

    # --- Rendering -----------------------------------------------------------

    def render(self) -> None:
        """Draw one frame: the shared world, then the current state's screen."""
        self.render_world()
        {
            GameState.START: self.render_start_screen,
            GameState.PLAYING: self.render_playing,
            GameState.GAME_OVER: self.render_game_over,
        }[self.state]()

    def render_world(self) -> None:
        """Draw the background, the pipes, the bird and the ground.

        Shared by every state, so the bird stays visible on the start and
        game-over screens and the world is still visible underneath the banners.
        """
        self.screen.fill(settings.BACKGROUND_COLOR)
        for pipe in self.pipes:
            pipe.draw(self.screen)
        self.player.draw(self.screen)
        self._draw_ground()

    def render_start_screen(self) -> None:
        """Attract screen: the title and a single start prompt."""
        self._draw_panel("FLAPPY BIRD", ["Press SPACE or Click to Start"])

    def render_playing(self) -> None:
        """Live play: the world plus the running score."""
        self._draw_score()

    def render_game_over(self) -> None:
        """Result screen: the final score, the best and a restart prompt."""
        self._draw_panel(
            "GAME OVER",
            [
                f"Score: {self.score}",
                f"Best: {self.high_score}",
                "Press SPACE or Click to Restart",
            ],
        )

    def _draw_ground(self) -> None:
        ground = pygame.Rect(
            0, settings.GROUND_TOP, settings.SCREEN_WIDTH, settings.GROUND_HEIGHT
        )
        pygame.draw.rect(self.screen, settings.GROUND_COLOR, ground)

    def _draw_score(self) -> None:
        label = self._render_text(f"Score: {self.score}")
        self.screen.blit(label, self._centered_x(label, settings.SCORE_TEXT_Y))

    def _render_text(self, text: str) -> pygame.Surface:
        return self.score_font.render(text, True, settings.TEXT_COLOR)

    def _centered_x(self, label: pygame.Surface, y: int) -> tuple[int, int]:
        return ((settings.SCREEN_WIDTH - label.get_width()) // 2, y)

    def _draw_panel(self, title: str, lines: list[str]) -> None:
        """Draw a centered translucent panel with a title and body lines."""
        title_label = self.banner_font.render(title, True, settings.TEXT_COLOR)
        line_labels = [
            self.banner_font.render(line, True, settings.TEXT_COLOR) for line in lines
        ]

        line_height = self.banner_font.get_height()
        padding = 20
        line_gap = 4
        width = max(
            [label.get_width() for label in [title_label, *line_labels]] + [0]
        ) + padding * 2
        height = (
            padding * 2
            + title_label.get_height()
            + (line_height + line_gap) * len(line_labels)
        )

        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((255, 255, 255, 220))

        y = padding
        panel.blit(title_label, (padding, y))
        y += title_label.get_height() + line_gap
        for label in line_labels:
            panel.blit(label, (padding, y))
            y += line_height + line_gap

        self.screen.blit(panel, centered_rect(panel, self.screen.get_size()))
