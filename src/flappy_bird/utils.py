"""Small dependency-free helpers shared across modules."""

import random
from collections.abc import Sequence
from typing import Protocol

from . import settings


class _Ticker(Protocol):
    """The part of ``pygame.time.Clock`` that :func:`frame_delta` needs.

    Declared here so this module keeps no Pygame import at all, while still
    saying exactly what it expects of the object it is handed.
    """

    def tick(self, fps: int) -> int: ...


class _Sized(Protocol):
    """Anything with a ``get_size()``: a ``Rect``, a ``Surface``, anything else."""

    def get_size(self) -> tuple[int, int]: ...


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Return ``value`` restricted to the inclusive ``minimum``/``maximum`` range."""
    if minimum > maximum:
        raise ValueError("minimum must not be greater than maximum")
    return max(minimum, min(maximum, value))


def frame_delta(clock: _Ticker, fps: int = settings.FPS) -> float:
    """Advance ``clock`` and return a clamped frame delta in seconds."""
    seconds = clock.tick(fps) / 1000.0
    return clamp(seconds, 0.0, settings.MAX_FRAME_TIME)


def random_gap_center(
    gap: int = settings.PIPE_GAP_SIZE,
    min_center: int = settings.PIPE_MIN_GAP_CENTER,
    max_center: int = settings.PIPE_MAX_GAP_CENTER,
    rng: random.Random | None = None,
) -> int:
    """Pick a random gap center between ``min_center`` and ``max_center``.

    The requested range is narrowed further when needed so the whole gap always
    fits between the ceiling and the ground.
    """
    half_gap = gap // 2
    lowest = max(min_center, settings.CEILING_Y + half_gap)
    highest = min(max_center, settings.GROUND_TOP - half_gap)
    if lowest > highest:
        raise ValueError("no room for a pipe gap within the requested range")
    return (rng or random).randint(lowest, highest)


def centered_rect(rect: _Sized, surface_size: Sequence[int]) -> tuple[int, int]:
    """Return the top-left corner that centers ``rect`` on ``surface_size``."""
    width, height = rect.get_size()
    surface_width, surface_height = surface_size
    return (
        (surface_width - width) // 2,
        (surface_height - height) // 2,
    )
