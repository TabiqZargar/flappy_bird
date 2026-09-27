"""The player (bird) entity."""

from __future__ import annotations

import pygame

from . import settings
from .utils import clamp


class Player:
    """A gravity-affected bird that responds to jump input."""

    def __init__(
        self,
        x: float = settings.BIRD_START_X,
        y: float = settings.BIRD_START_Y,
        width: int = settings.BIRD_WIDTH,
        height: int = settings.BIRD_HEIGHT,
        radius: int = settings.BIRD_RADIUS,
    ) -> None:
        self.width = width
        self.height = height
        self.radius = radius
        self.x = float(x)
        self.y = float(y)
        self.velocity_y = 0.0
        self.reset()

    # --- State ---------------------------------------------------------------

    def reset(self) -> None:
        """Return the player to its starting position and clear momentum."""
        self.x = float(settings.BIRD_START_X)
        self.y = float(settings.BIRD_START_Y)
        self.velocity_y = 0.0

    @property
    def rect(self) -> pygame.Rect:
        """Axis-aligned bounding box centered on the player position."""
        return pygame.Rect(
            round(self.x) - self.width // 2,
            round(self.y) - self.height // 2,
            self.width,
            self.height,
        )

    @property
    def position(self) -> tuple[int, int]:
        return round(self.x), round(self.y)

    @property
    def is_out_of_bounds(self) -> bool:
        return self.y < 0 or self.y > settings.SCREEN_HEIGHT

    # --- Behaviour -----------------------------------------------------------

    def jump(self, strength: float = settings.BIRD_JUMP_VELOCITY) -> None:
        """Apply an instantaneous upward impulse."""
        self.velocity_y = strength

    def update(self, dt: float) -> None:
        """Advance gravity and vertical motion by ``dt`` seconds."""
        self.velocity_y = clamp(
            self.velocity_y + settings.GRAVITY * dt,
            -abs(settings.BIRD_JUMP_VELOCITY) * 10,
            settings.MAX_FALL_SPEED,
        )
        self.y += self.velocity_y * dt

    # --- Rendering -----------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the bird as a placeholder circle with an outline."""
        pygame.draw.circle(
            surface,
            settings.BIRD_OUTLINE_COLOR,
            self.position,
            self.radius + 2,
        )
        pygame.draw.circle(surface, settings.BIRD_COLOR, self.position, self.radius)
