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
        """Draw both halves as capped, lit columns.

        Every piece is drawn *inside* its collision rectangle, so the hitbox can
        never look wrong or play differently. That includes the cap, which is
        kept flush with the shaft rather than made to overhang: a wider cap would
        read as a bigger target than the one the bird actually has to clear.
        """
        top_rect, bottom_rect = self.rects
        if top_rect.width > 0 and top_rect.height > 0:
            self._draw_column(surface, top_rect, cap_at_bottom=True)
        if bottom_rect.width > 0 and bottom_rect.height > 0:
            self._draw_column(surface, bottom_rect, cap_at_bottom=False)

    def _draw_column(
        self, surface: pygame.Surface, rect: pygame.Rect, cap_at_bottom: bool
    ) -> None:
        """One vertical half: shaft, cap, highlight, shadow and edges.

        ``cap_at_bottom`` says which end of the column faces the gap, so the cap
        is always drawn next to the opening the bird has to fly through.
        """
        block = settings.PIXEL_SCALE
        pygame.draw.rect(surface, self.color, rect)

        cap_height = min(settings.PIPE_CAP_HEIGHT, rect.height)
        # A cap only reads as a cap when there is shaft left above and below it.
        if rect.height > cap_height * 2:
            if cap_at_bottom:
                cap_rect = pygame.Rect(
                    rect.x, rect.bottom - cap_height, rect.width, cap_height
                )
                inner_edge = cap_rect.top
            else:
                cap_rect = pygame.Rect(rect.x, rect.y, rect.width, cap_height)
                inner_edge = cap_rect.bottom - block
            pygame.draw.rect(surface, settings.PIPE_CAP_COLOR, cap_rect)
            self._shade(surface, cap_rect)
            # A hard line on the gap-facing side, so the opening reads as an edge
            # rather than a change of colour.
            pygame.draw.rect(
                surface,
                settings.PIPE_EDGE_COLOR,
                pygame.Rect(rect.x, inner_edge, rect.width, block),
            )

        self._shade(surface, rect)

    def _shade(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Highlight, shadow and hard edges, all inside ``rect``.

        The widths are clamped so a narrow or degenerate rectangle cannot make a
        strip wrap around or spill outside the collision box.
        """
        block = settings.PIXEL_SCALE
        usable = rect.width - block * 2

        highlight_width = min(settings.PIPE_HIGHLIGHT_WIDTH, usable)
        if highlight_width > 0:
            pygame.draw.rect(
                surface,
                settings.PIPE_HIGHLIGHT_COLOR,
                pygame.Rect(rect.x + block, rect.y, highlight_width, rect.height),
            )

        shadow_width = min(settings.PIPE_SHADOW_WIDTH, usable)
        if shadow_width > 0:
            pygame.draw.rect(
                surface,
                settings.PIPE_SHADOW_COLOR,
                pygame.Rect(
                    rect.right - block - shadow_width,
                    rect.y,
                    shadow_width,
                    rect.height,
                ),
            )

        # Edges last, so they stay crisp over the shading.
        pygame.draw.rect(
            surface,
            settings.PIPE_EDGE_COLOR,
            pygame.Rect(rect.x, rect.y, block, rect.height),
        )
        pygame.draw.rect(
            surface,
            settings.PIPE_EDGE_COLOR,
            pygame.Rect(rect.right - block, rect.y, block, rect.height),
        )
