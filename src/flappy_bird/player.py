"""The player (bird) entity: float position, vertical velocity and flap physics.

All motion is integrated against a delta time in seconds, so behaviour is the
same regardless of the frame rate the game happens to run at.
"""

from __future__ import annotations

import pygame

from . import settings
from .visuals import draw_bird


class Player:
    """A gravity-affected bird that responds to flap input."""

    def __init__(
        self,
        x: float = settings.BIRD_START_X,
        y: float = settings.BIRD_START_Y,
        size: int = settings.BIRD_SIZE,
    ) -> None:
        self.size = size
        self.x = float(x)
        self.y = float(y)
        self.velocity_y = 0.0

    # --- State ---------------------------------------------------------------

    def reset(self) -> None:
        """Return the player to its starting position and clear momentum."""
        self.x = float(settings.BIRD_START_X)
        self.y = float(settings.BIRD_START_Y)
        self.velocity_y = 0.0

    @property
    def radius(self) -> float:
        return self.size / 2.0

    @property
    def rect(self) -> pygame.Rect:
        """Axis-aligned bounding box centered on the player position."""
        return pygame.Rect(
            round(self.x) - self.size // 2,
            round(self.y) - self.size // 2,
            self.size,
            self.size,
        )

    @property
    def position(self) -> tuple[int, int]:
        return round(self.x), round(self.y)

    @property
    def top(self) -> float:
        return self.y - self.radius

    @property
    def bottom(self) -> float:
        return self.y + self.radius

    # --- Boundaries ----------------------------------------------------------

    @property
    def hit_ceiling(self) -> bool:
        """True once the bird has risen above the playable area."""
        return self.top <= settings.CEILING_Y

    @property
    def hit_ground(self) -> bool:
        """True once the bird has fallen far enough to touch the ground."""
        return self.bottom >= settings.GROUND_TOP

    @property
    def is_out_of_bounds(self) -> bool:
        return self.hit_ceiling or self.hit_ground

    # --- Behaviour -----------------------------------------------------------

    def jump(self, velocity: float = settings.JUMP_VELOCITY) -> None:
        """Set the upward velocity for a flap.

        The velocity is assigned rather than accumulated, so flapping repeatedly
        can never build up a runaway speed.
        """
        self.velocity_y = velocity

    def update(self, dt: float) -> None:
        """Integrate gravity and vertical motion over ``dt`` seconds."""
        self.velocity_y = min(
            self.velocity_y + settings.GRAVITY * dt,
            settings.MAX_FALL_SPEED,
        )
        self.y += self.velocity_y * dt

    # --- Rendering -----------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the bird sprite centred on the player position.

        The sprite is tilted from ``velocity_y`` for flavour only; the collision
        rectangle is a plain axis-aligned box and is never rotated.
        """
        draw_bird(surface, self.x, self.y, self.velocity_y)
