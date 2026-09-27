"""Progressive difficulty: how the pipe parameters tighten as the score climbs.

The entire model is a pure function of the score, and it only ever *produces
numbers*. Nothing in this module moves a pipe, spawns anything, keeps a timer or
looks at the game state, which is what makes it cheap to call every frame and
trivial to test in isolation.

Why it is a lookup table and not arithmetic on each call: there are only
``DIFFICULTY_MAX_LEVEL + 1`` distinct answers, so they are built once at import
and :func:`get_difficulty` is a clamp plus a tuple index. It allocates nothing.

The progression is deliberately gentle. Speed rises by
``DIFFICULTY_SPEED_INCREMENT`` per level, the gap shrinks by
``DIFFICULTY_GAP_DECREMENT``, and pipes arrive a little sooner, but the last
level is still comfortably playable: a 33% faster scroll, a gap three times the
bird, and 192 px of space between pipe pairs. The clamps are not decoration --
they are what stop a very long run from turning the game into a wall.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import settings


@dataclass(frozen=True)
class DifficultyProfile:
    """The effective pipe parameters for one difficulty level.

    Frozen so a profile is a value: it can be compared, cached and shared between
    every pipe spawned at that level without anyone being able to edit it
    afterwards. ``spacing`` is the distance the world scrolls between one pipe
    pair and the next, and is the number that has to stay larger than the gap for
    consecutive pairs to remain reachable.
    """

    level: int
    pipe_speed: float
    pipe_gap: int
    spawn_interval: float

    @property
    def spacing(self) -> float:
        """Distance in pixels between the left edges of consecutive pipe pairs."""
        return self.spawn_interval * self.pipe_speed

    @property
    def is_maximum(self) -> bool:
        """True once further score cannot make the game harder."""
        return self.level >= settings.DIFFICULTY_MAX_LEVEL


def difficulty_level(score: int) -> int:
    """Return the difficulty level earned by ``score``.

    One level per ``DIFFICULTY_SCORE_STEP`` points, never above
    ``DIFFICULTY_MAX_LEVEL``. Negative scores (which a mis-wired caller could
    produce) are treated as zero, so the result is always a valid table index.
    """
    level = int(score) // settings.DIFFICULTY_SCORE_STEP
    return max(0, min(level, settings.DIFFICULTY_MAX_LEVEL))


def _build_profiles() -> tuple[DifficultyProfile, ...]:
    """Build the whole ladder once, clamping every step to its configured bound.

    Each bound is reached exactly at ``DIFFICULTY_MAX_LEVEL``, so the clamps are
    the guarantee that level 5 is the end of the road rather than a coincidence
    of the chosen numbers.
    """
    return tuple(
        DifficultyProfile(
            level=level,
            pipe_speed=min(
                settings.PIPE_SPEED + level * settings.DIFFICULTY_SPEED_INCREMENT,
                settings.DIFFICULTY_MAX_SPEED,
            ),
            pipe_gap=max(
                int(
                    settings.PIPE_GAP_SIZE
                    - level * settings.DIFFICULTY_GAP_DECREMENT
                ),
                settings.DIFFICULTY_MIN_GAP,
            ),
            spawn_interval=max(
                settings.PIPE_SPAWN_INTERVAL
                - level * settings.DIFFICULTY_SPAWN_DECREMENT,
                settings.DIFFICULTY_MIN_SPAWN_INTERVAL,
            ),
        )
        for level in range(settings.DIFFICULTY_MAX_LEVEL + 1)
    )


#: The whole ladder, built once at import. Index 0 is the original game.
_PROFILES: tuple[DifficultyProfile, ...] = _build_profiles()

#: The profile a fresh round starts from, and the one a restart returns to.
BASELINE = _PROFILES[0]
#: The hardest the game ever gets. Every score beyond it maps here.
MAXIMUM = _PROFILES[-1]


def profile_for_level(level: int) -> DifficultyProfile:
    """Return the profile for an explicit level, clamped to the valid range."""
    return _PROFILES[max(0, min(int(level), settings.DIFFICULTY_MAX_LEVEL))]


def get_difficulty(score: int) -> DifficultyProfile:
    """Return the pipe parameters that ``score`` has earned.

    This is the single entry point the game uses. It is a pure function: the same
    score always yields the very same profile object, so it is safe to call every
    frame and to compare by identity.
    """
    return _PROFILES[difficulty_level(score)]


def all_profiles() -> tuple[DifficultyProfile, ...]:
    """Every level from baseline to maximum, in order. Handy for tests and docs."""
    return _PROFILES
