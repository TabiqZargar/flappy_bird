"""Collision checks between the bird and the pipes.

The rules follow Pygame's ``Rect.colliderect``: two rectangles collide only when
they overlap on both axes with a positive area. Rectangles that merely share an
edge or a corner do **not** collide, so a hitbox resting exactly against a pipe
edge still passes and one pixel of penetration does not.
"""

from __future__ import annotations

from typing import Iterable

from .pipe import Pipe
from .player import Player


def check_pipe_collision(player: Player, pipe: Pipe) -> bool:
    """True when the bird's hitbox touches or overlaps either pipe column."""
    hitbox = player.rect
    return any(hitbox.colliderect(column) for column in pipe.rects)


def check_any_pipe_collision(player: Player, pipes: Iterable[Pipe]) -> bool:
    """True when the bird hits at least one of ``pipes``."""
    return any(check_pipe_collision(player, pipe) for pipe in pipes)
