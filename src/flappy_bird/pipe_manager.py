"""Spawning, timing and lifetime management for pipes.

The manager owns the pipe list, so :class:`~flappy_bird.game.Game` only has to
call :meth:`PipeManager.update` and draw whatever it holds.

Difficulty arrives from outside as a ready-made
:class:`~flappy_bird.difficulty.DifficultyProfile`. The manager never looks at
the score and never works out a level itself -- it only reads the three numbers
it has been handed and uses them for *future* pipes:

* a pipe keeps the speed and gap it was born with, so nothing in flight ever
  changes shape or pace mid-flight;
* the spawn interval is read at spawn time, so the next pipe goes out on the
  current beat.

Passing explicit ``spawn_interval``/``speed``/``gap`` values pins the manager to
those numbers and switches difficulty off, which is how fixed-scenario managers
(including several existing tests) keep a reproducible world.
"""

from __future__ import annotations

import random

from . import settings
from .difficulty import DifficultyProfile, get_difficulty
from .pipe import Pipe
from .utils import random_gap_center


class PipeManager:
    """Emits pipes on a timer and recycles the ones that leave the screen."""

    MAX_SPAWNS_PER_UPDATE = 3

    def __init__(
        self,
        spawn_interval: float | None = None,
        speed: float | None = None,
        gap: int | None = None,
        spawn_x: float = settings.SCREEN_WIDTH,
        min_gap_center: int = settings.PIPE_MIN_GAP_CENTER,
        max_gap_center: int = settings.PIPE_MAX_GAP_CENTER,
        max_spawns_per_update: int = MAX_SPAWNS_PER_UPDATE,
        rng: random.Random | None = None,
        difficulty: DifficultyProfile | None = None,
    ) -> None:
        if spawn_interval is not None and spawn_interval <= 0:
            raise ValueError("spawn_interval must be greater than zero")
        if speed is not None and speed <= 0:
            raise ValueError("speed must be greater than zero")
        if gap is not None and gap <= 0:
            raise ValueError("gap must be greater than zero")
        self._spawn_interval = spawn_interval
        self._speed = speed
        self._gap = gap
        self.spawn_x = spawn_x
        self.min_gap_center = min_gap_center
        self.max_gap_center = max_gap_center
        self.max_spawns_per_update = max_spawns_per_update
        self.rng = rng or random.Random()
        self.pipes: list[Pipe] = []
        self.elapsed = 0.0
        # A fresh manager starts at the level-0 profile, so a manager that is
        # never told otherwise behaves exactly like the original game.
        self.difficulty = get_difficulty(0) if difficulty is None else difficulty

    # --- Difficulty -----------------------------------------------------------

    def set_difficulty(self, profile: DifficultyProfile) -> None:
        """Adopt a new profile. Only pipes spawned from now on are affected."""
        self.difficulty = profile

    @property
    def spawn_interval(self) -> float:
        """Seconds between pipes.

        The pinned value, else the current profile's. A pinned manager ignores
        the profile entirely, so a fixed scenario stays bit-for-bit reproducible.
        """
        if self._spawn_interval is not None:
            return self._spawn_interval
        if self.is_pinned:
            return settings.PIPE_SPAWN_INTERVAL
        return self.difficulty.spawn_interval

    @spawn_interval.setter
    def spawn_interval(self, value: float) -> None:
        if value <= 0:
            raise ValueError("spawn_interval must be greater than zero")
        self._spawn_interval = value

    @property
    def speed(self) -> float:
        """Pipe speed for *new* pipes: the pinned value, else the profile's."""
        if self._speed is not None:
            return self._speed
        if self.is_pinned:
            return settings.PIPE_SPEED
        return self.difficulty.pipe_speed

    @speed.setter
    def speed(self, value: float) -> None:
        if value <= 0:
            raise ValueError("speed must be greater than zero")
        self._speed = value

    @property
    def gap(self) -> int:
        """Gap size for *new* pipes: the pinned value, else the profile's."""
        if self._gap is not None:
            return self._gap
        if self.is_pinned:
            return settings.PIPE_GAP_SIZE
        return self.difficulty.pipe_gap

    @gap.setter
    def gap(self, value: int) -> None:
        if value <= 0:
            raise ValueError("gap must be greater than zero")
        self._gap = value

    @property
    def is_pinned(self) -> bool:
        """True when explicit values fix the manager and switch difficulty off.

        Giving *any* of ``spawn_interval``/``speed``/``gap`` pins the whole
        manager to the original pipe constants for the values left unspecified.
        That keeps a deliberately scripted scenario (a fixed gap band, a seeded
        rng) reproducible no matter how many points it scores, while a manager
        left entirely at its defaults tracks the difficulty ladder.
        """
        return (
            self._spawn_interval is not None
            or self._speed is not None
            or self._gap is not None
        )

    # --- Lifetime ------------------------------------------------------------

    def reset(self) -> None:
        """Drop every pipe, restart the spawn timer and return to baseline.

        Difficulty goes back to level 0 as well, so a new round always starts as
        the original game no matter how far the last one got.
        """
        self.pipes.clear()
        self.elapsed = 0.0
        self.difficulty = get_difficulty(0)

    # --- Behaviour -----------------------------------------------------------

    def spawn(self) -> Pipe:
        """Create a pipe at the right edge with a random gap and keep it.

        The speed and gap are read once, here, and copied onto the pipe. They are
        never touched again, which is what keeps a pipe in flight internally
        consistent even if the difficulty changes on the very next frame.
        """
        gap = self.gap
        pipe = Pipe(
            x=self.spawn_x,
            gap_y=random_gap_center(
                gap=gap,
                min_center=self.min_gap_center,
                max_center=self.max_gap_center,
                rng=self.rng,
            ),
            gap=gap,
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
