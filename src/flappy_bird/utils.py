"""Small dependency-free helpers shared across modules."""

import random
from typing import Sequence

from . import settings


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Return ``value`` restricted to the inclusive ``minimum``/``maximum`` range."""
    if minimum > maximum:
        raise ValueError("minimum must not be greater than maximum")
    return max(minimum, min(maximum, value))


def frame_delta(clock, fps: int = settings.FPS) -> float:
    """Advance ``clock`` and return a clamped frame delta in seconds."""
    seconds = clock.tick(fps) / 1000.0
    return clamp(seconds, 0.0, settings.MAX_FRAME_TIME)


def random_gap_center(
    gap: int = settings.PIPE_GAP,
    screen_height: int = settings.SCREEN_HEIGHT,
    min_edge: int = settings.PIPE_MIN_EDGE,
    rng: random.Random | None = None,
) -> int:
    """Pick a random vertical center for a pipe gap that stays fully on screen."""
    lowest = min_edge + gap // 2
    highest = screen_height - min_edge - gap // 2
    if lowest > highest:
        raise ValueError("pipe gap does not fit on screen")
    return (rng or random).randint(lowest, highest)


def centered_rect(
    rect, surface_size: Sequence[int]
) -> tuple[int, int]:
    """Return the top-left corner that centers ``rect`` (Rect or Surface) on ``surface_size``."""
    width, height = rect.get_size()
    surface_width, surface_height = surface_size
    return (
        (surface_width - width) // 2,
        (surface_height - height) // 2,
    )
