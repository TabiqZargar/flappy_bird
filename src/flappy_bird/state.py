"""The game's lifecycle states.

The state is the single source of truth for what the game is doing:
:class:`~flappy_bird.game.Game` consults it to decide whether to simulate the
world, what a press of the flap key means, and which screen to draw.
"""

from __future__ import annotations

from enum import Enum


class GameState(Enum):
    """Where the game currently is in its start/play/die cycle.

    - ``START``: the attract screen. The bird is visible but the world is
      frozen, and no pipe has ever been spawned.
    - ``PLAYING``: the live round. Physics, pipes and scoring all run.
    - ``GAME_OVER``: the round ended. The world stays frozen until a press.
    """

    START = "start"
    PLAYING = "playing"
    GAME_OVER = "game_over"

    @property
    def is_over(self) -> bool:
        """True while the round has ended."""
        return self is GameState.GAME_OVER

    @property
    def is_playing(self) -> bool:
        """True while the simulation should advance."""
        return self is GameState.PLAYING
