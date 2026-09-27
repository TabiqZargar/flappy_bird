"""Pipe entity: gap geometry, horizontal movement and drawing.

Spawning and lifetime are owned by :class:`~flappy_bird.pipe_manager.PipeManager`.
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
        gap: int = settings.PIPE_GAP_SIZE,
        top_y: int = settings.CEILING_Y,
        bottom_y: int = settings.GROUND_TOP,
        speed: float = settings.PIPE_SPEED,
        color: tuple[int, int, int] = settings.PIPE_COLOR,
    ) -> None:
        self.x = float(x)
        self.gap_y = int(gap_y)
        self.width = width
        self.gap = gap
        self.top_y = top_y
        self.bottom_y = bottom_y
        self.speed = speed
        self.color = color
        self.scored = False

    # --- Geometry ------------------------------------------------------------

    @property
    def gap_top(self) -> int:
        return self.gap_y - self.gap // 2

    @property
    def gap_bottom(self) -> int:
        return self.gap_y + self.gap // 2

    @property
    def top_rect(self) -> pygame.Rect:
        """Column running from the top of the playable area to the gap."""
        return pygame.Rect(
            round(self.x),
            self.top_y,
            self.width,
            max(self.gap_top - self.top_y, 0),
        )

    @property
    def bottom_rect(self) -> pygame.Rect:
        """Column running from the gap down to the ground."""
        return pygame.Rect(
            round(self.x),
            self.gap_bottom,
            self.width,
            max(self.bottom_y - self.gap_bottom, 0),
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
