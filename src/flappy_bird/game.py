"""Game lifecycle: window, states, main loop, input, update and rendering."""

from __future__ import annotations

import os

import pygame

from . import settings
from .audio import AudioManager, pre_init_mixer
from .collision import check_any_pipe_collision
from .difficulty import DifficultyProfile, get_difficulty
from .pipe import Pipe
from .pipe_manager import PipeManager
from .player import Player
from .scoring import count_newly_passed
from .state import GameState
from .utils import frame_delta
from .visuals import Visuals

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
    the attract screen runs no physics and the game-over screen is a frozen
    world. The attract screen is not frozen *visually*, though: the scenery
    drifts and the bird idles, because a still title card reads as a pause.
    """

    def __init__(self, headless: bool = False) -> None:
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        else:
            # Must come before pygame.init(), which opens the mixer on its own.
            pre_init_mixer()

        pygame.init()
        pygame.display.set_caption(settings.CAPTION)
        self.screen = pygame.display.set_mode(
            (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        )
        self.clock = pygame.time.Clock()

        self.player = Player()
        self.pipe_manager = PipeManager()
        self.visuals = Visuals()
        # Headless runs get a silent manager: opening a device nobody can hear
        # would only slow the suite down.
        self.audio = AudioManager(enabled=not headless)
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
    def difficulty(self) -> DifficultyProfile:
        """Pipe parameters the current score has earned.

        Read-only on purpose: the game pushes profiles into the pipe manager and
        nothing reads a level back to make a decision, so the score stays the one
        and only source of truth.
        """
        return self.pipe_manager.difficulty

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

    def sync_difficulty(self) -> DifficultyProfile:
        """Push the profile the current score has earned into the pipe manager.

        Called at the end of every playing frame, after scoring, and the order
        matters:

        1. pipes move and new ones spawn for this frame;
        2. collision is checked, and a crash returns before scoring;
        3. points are awarded;
        4. only then is the profile refreshed.

        So a point earned on frame N can never reshape the pipe that paid it --
        that pipe is already on screen with the geometry it spawned with -- and
        the new profile first applies to the next pipe to be spawned. The refresh
        is a clamp and a tuple index, and assigning a shared profile is a
        reference store, so calling it every frame costs nothing measurable.
        """
        profile = get_difficulty(self.score)
        self.pipe_manager.set_difficulty(profile)
        return profile

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
        elif key == pygame.K_m:
            self.toggle_mute()
        elif key in FLAP_KEYS:
            self.handle_action()
        elif key == pygame.K_r:
            self.restart()

    def handle_mouse_down(self, button: int) -> None:
        """Left click acts; right and middle clicks are ignored."""
        if button == 1:
            self.handle_action()

    def toggle_mute(self) -> bool:
        """Flip the mute flag and report the new value.

        Bound to ``M`` and valid in every state: it touches nothing but the audio
        manager, so it can never disturb the round, the score or the physics.
        """
        return self.audio.toggle_mute()

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
        self.audio.play_flap()

    # --- Loop stages ---------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the simulation by ``dt`` seconds while playing.

        The decoration always ticks outside the game-over screen, so the attract
        screen is alive and the world settles once the round is lost. Only the
        world itself is frozen outside ``PLAYING``: no physics, no pipes, no
        scoring.

        ``animate_bird`` is therefore true for ``START`` as well: there is no
        velocity to tilt a wing against on the attract screen, so the wing beat is
        the only life the sprite has. It changes nothing physical, because the
        start screen has no player motion to animate.
        """
        frozen = self.state is GameState.GAME_OVER
        self.visuals.update(
            dt,
            animate_bird=not frozen,
            drift_clouds=not frozen,
        )
        if not self.state.is_playing:
            return

        self.player.update(dt)
        self.pipe_manager.update(dt)

        if self.player.is_out_of_bounds or check_any_pipe_collision(
            self.player, self.pipes
        ):
            self.end_round()
            return

        awarded = count_newly_passed(self.player, self.pipes)
        if awarded:
            self.add_score(awarded)
            # One chime per scoring event, however many points it was worth, so
            # simultaneous pipes cannot stack up into a noise burst.
            self.audio.play_score()
            self.visuals.pulse_score()

        # Last: the pipes for this frame are already on their way, so the score
        # just earned only ever affects pipes spawned from the next frame on.
        self.sync_difficulty()

    def end_round(self) -> None:
        """Move to ``GAME_OVER`` and announce it exactly once.

        The guard is what makes the sequence idempotent: ``update`` returns
        immediately afterwards, so a frozen game-over screen can never replay the
        crash sounds.
        """
        if self.state is GameState.GAME_OVER:
            return
        self.state = GameState.GAME_OVER
        self.audio.play_hit()
        self.audio.play_game_over()

    # --- Rendering -----------------------------------------------------------

    def render(self) -> None:
        """Draw one frame: the shared world, then the current state's screen."""
        # On the attract screen the world bird stands in for the title bird, so
        # it is left out of the shared pass to avoid two birds in one frame.
        attract = self.state is GameState.START
        self.render_world(show_bird=not attract)
        {
            GameState.START: self.render_start_screen,
            GameState.PLAYING: self.render_playing,
            GameState.GAME_OVER: self.render_game_over,
        }[self.state]()

    def render_world(self, show_bird: bool = True) -> None:
        """Draw the background, the pipes, the bird and the ground.

        Shared by every state, back to front: sky, distant scenery, clouds, pipes,
        bird, ground. The world is still visible underneath the start and
        game-over cards, and the ground is last so it always covers the bottom of
        the pipes.
        """
        self.visuals.draw_sky(self.screen)
        self.visuals.draw_distant(self.screen)
        self.visuals.draw_clouds(self.screen)
        for pipe in self.pipes:
            pipe.draw(self.screen)
        if show_bird:
            self.visuals.draw_bird(self.screen, self.player)
        self.visuals.draw_ground(self.screen)

    def render_start_screen(self) -> None:
        """Attract screen: a title, an idle bird and a start prompt in a card."""
        self.visuals.draw_title_bird(self.screen)
        self.visuals.draw_centered_text(
            self.screen,
            "FLAPPY BIRD",
            settings.TITLE_TEXT_Y,
            settings.TITLE_TEXT_SCALE,
            settings.TEXT_TITLE_COLOR,
        )
        if self.high_score:
            self.visuals.draw_centered_text(
                self.screen,
                f"BEST: {self.high_score}",
                settings.TITLE_BEST_Y,
                settings.PANEL_TEXT_SCALE,
                settings.TEXT_COLOR,
                shadow=None,
            )
        prompt = "PRESS SPACE TO START"
        if not self.visuals.prompt_visible:
            prompt = ""
        card_rect = self._draw_prompt_card(prompt)
        hint_y = card_rect.bottom + settings.TITLE_HINT_GAP
        self.visuals.draw_centered_text(
            self.screen,
            "CLICK OR W TO FLAP",
            hint_y,
            settings.PANEL_TEXT_SCALE,
            settings.TEXT_HINT_COLOR,
            shadow=None,
        )

    def render_playing(self) -> None:
        """Live play: the world plus the running score."""
        self._draw_score()
        self._draw_difficulty()

    def _draw_difficulty(self) -> None:
        """Draw a quiet level readout under the score.

        Six possible strings, so the text cache holds one extra entry at most and
        a long run cannot grow it.
        """
        label = self.visuals.text.render(
            self.visuals.labeler(settings.DIFFICULTY_TEXT_SCALE),
            f"Difficulty {self.difficulty.level}",
            settings.DIFFICULTY_TEXT_COLOR,
        )
        self.screen.blit(label, self._centered_x(label, settings.DIFFICULTY_TEXT_Y))

    def render_game_over(self) -> None:
        """Result screen: the final score, the best and a restart prompt."""
        self._draw_panel(
            "GAME OVER",
            [
                f"Score: {self.score}",
                f"Best: {self.high_score}",
                "Press SPACE to Restart",
            ],
        )

    def _draw_ground(self) -> None:
        self.visuals.draw_ground(self.screen)

    def _draw_score(self) -> None:
        label = self.visuals.text.render(
            self.visuals.labeler(settings.SCORE_TEXT_SCALE),
            f"Score: {self.score}",
            self.visuals.score_color(),
        )
        self.screen.blit(label, self._centered_x(label, settings.SCORE_TEXT_Y))

    def _centered_x(self, label: pygame.Surface, y: int) -> tuple[int, int]:
        return ((settings.SCREEN_WIDTH - label.get_width()) // 2, y)

    def _draw_panel(self, title: str, lines: list[str]) -> None:
        """Draw a centered blocky card with a title and body lines."""
        self.visuals.panels.draw(
            self.screen,
            title,
            lines,
            self.visuals.labeler(settings.PANEL_TITLE_SCALE),
            self.visuals.labeler(settings.PANEL_TEXT_SCALE),
            settings.TEXT_COLOR,
        )

    def _draw_prompt_card(self, prompt: str) -> pygame.Rect:
        panel = self.visuals.panels.render(
            "",
            [prompt] if prompt else [""],
            self.visuals.labeler(settings.PANEL_TITLE_SCALE),
            self.visuals.labeler(settings.PANEL_TEXT_SCALE),
            settings.TEXT_COLOR,
        )
        rect = panel.get_rect(
            centerx=settings.SCREEN_WIDTH // 2, top=settings.TITLE_PROMPT_CARD_TOP
        )
        self.screen.blit(panel, rect)
        return rect
