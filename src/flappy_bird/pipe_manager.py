"""Spawning, timing and lifetime management for pipes.

The manager owns the pipe list, so :class:`~flappy_bird.game.Game` only has to
call :meth:`PipeManager.update` and draw whatever it holds.
"""

from __future__ import annotations

import random

from . import settings
from .pipe import Pipe
from .utils import random_gap_center


class PipeManager:
    """Emits pipes on a timer and recycles the ones that leave the screen."""

    MAX_SPAWNS_PER_UPDATE = 3

    def __init__(
        self,
        spawn_interval: float = settings.PIPE_SPAWN_INTERVAL,
        speed: float = settings.PIPE_SPEED,
        spawn_x: float = settings.SCREEN_WIDTH,
        max_spawns_per_update: int = MAX_SPAWNS_PER_UPDATE,
        rng: random.Random | None = None,
    ) -> None:
        if spawn_interval <= 0:
            raise ValueError("spawn_interval must be greater than zero")
        self.spawn_interval = spawn_interval
        self.speed = speed
        self.spawn_x = spawn_x
        self.max_spawns_per_update = max_spawns_per_update
        self.rng = rng or random.Random()
        self.pipes: list[Pipe] = []
        self.elapsed = 0.0

    # --- Lifetime ------------------------------------------------------------

    def reset(self) -> None:
        """Drop every pipe and restart the spawn timer."""
        self.pipes.clear()
        self.elapsed = 0.0

    # --- Behaviour -----------------------------------------------------------

    def spawn(self) -> Pipe:
        """Create a pipe at the right edge with a random gap and keep it."""
        pipe = Pipe(
            x=self.spawn_x,
            gap_y=random_gap_center(rng=self.rng),
            speed=self.speed,
        )
        self.pipes.append(pipe)
        return pipe

    def update(self, dt: float) -> int:
        """Move existing pipes, recycle the spent ones and emit new ones.

        Returns the number of pipes created by this call.
        """
        for pipe in self.pipes:
            pipe.update(dt)
        self.pipes = [pipe for pipe in self.pipes if not pipe.is_off_screen]
        return self.spawn_due(dt)

    def spawn_due(self, dt: float) -> int:
        """Advance the timer and spawn every pipe it owes. Returns the count.

        At most ``max_spawns_per_update`` pipes are created per call, so a large
        ``dt`` (a stall, or a debugger pause) cannot flood the screen. Any
        leftover time beyond that budget is discarded instead of piling up.
        """
        self.elapsed += dt

        spawned = 0
        while (
            self.elapsed >= self.spawn_interval
            and spawned < self.max_spawns_per_update
        ):
            self.spawn()
            self.elapsed -= self.spawn_interval
            spawned += 1

        if self.elapsed >= self.spawn_interval:
            self.elapsed = 0.0
        return spawned

    # --- Introspection -------------------------------------------------------

    @property
    def next_spawn_in(self) -> float:
        """Seconds remaining until the next pipe is emitted."""
        return max(self.spawn_interval - self.elapsed, 0.0)

    def __len__(self) -> int:
        return len(self.pipes)
