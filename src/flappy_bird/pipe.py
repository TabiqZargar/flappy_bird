"""Pipe entity placeholder.

Generation, spacing and scoring live here for later; the current version only
handles geometry, horizontal movement and drawing.
"""

from __future__ import annotations

import pygame

from . import settings


class Pipe:
    """A top/bottom pipe pair with a gap the player must fly through."""

    def __init__(
        self,
        x: float,
        gap_y: int,
        width: int = settings.PIPE_WIDTH,
        gap: int = settings.PIPE_GAP,
        height: int = settings.SCREEN_HEIGHT,
        speed: float = settings.PIPE_SPEED,
        color: tuple[int, int, int] = settings.PIPE_COLOR,
    ) -> None:
        self.x = float(x)
        self.gap_y = int(gap_y)
        self.width = width
        self.gap = gap
        self.height = height
        self.speed = speed
        self.color = color
        self.scored = False

    # --- Geometry ------------------------------------------------------------

    @property
    def top_rect(self) -> pygame.Rect:
        top_height = self.gap_y - self.gap // 2
        return pygame.Rect(round(self.x), 0, self.width, max(top_height, 0))

    @property
    def bottom_rect(self) -> pygame.Rect:
        top_height = self.gap_y - self.gap // 2
        bottom_y = top_height + self.gap
        return pygame.Rect(
            round(self.x), bottom_y, self.width, max(self.height - bottom_y, 0)
        )

    @property
    def rects(self) -> tuple[pygame.Rect, pygame.Rect]:
        return self.top_rect, self.bottom_rect

    @property
    def is_off_screen(self) -> bool:
        return self.x + self.width <= 0

    def has_behind(self, x: float) -> bool:
        """True once ``x`` has travelled past the pipe (used for scoring)."""
        return x > self.x + self.width

    # --- Behaviour -----------------------------------------------------------

    def update(self, dt: float) -> None:
        """Scroll the pipe leftwards by ``dt`` seconds."""
        self.x -= self.speed * dt

    # --- Rendering -----------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        for rect in self.rects:
            if rect.width <= 0 or rect.height <= 0:
                continue
            pygame.draw.rect(surface, self.color, rect)
            pygame.draw.rect(surface, settings.PIPE_EDGE_COLOR, rect, 3)
