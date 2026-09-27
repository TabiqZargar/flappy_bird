"""Scoring rules: exactly one point per pipe pair the bird gets behind.

Kept apart from :mod:`flappy_bird.collision`, because getting past a pipe is a
different question from hitting one.

Each :class:`~flappy_bird.pipe.Pipe` carries its own ``scored`` flag. That flag
is its scoring identity: pipes keep moving, so their x coordinate is not a
reliable key, and a per-pipe latch means a pipe can never pay out twice. Only
the running totals are held by the game.
"""

from __future__ import annotations

from typing import Iterable

from .pipe import Pipe
from .player import Player


def count_newly_passed(player: Player, pipes: Iterable[Pipe]) -> int:
    """Mark every pipe the bird has got behind and return how many were new.

    A pipe counts as passed once its right edge is behind the bird. Calling
    this again on the same pipes returns 0, so a pipe pays out exactly once.
    """
    newly_passed = 0
    for pipe in pipes:
        if pipe.scored or not pipe.has_behind(player.x):
            continue
        pipe.scored = True
        newly_passed += 1
    return newly_passed
