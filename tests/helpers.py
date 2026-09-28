"""Helpers shared by more than one test module.

Anything defined here is deliberately identical across the files that used to
carry their own copy: a single definition means a fix to the test scaffolding
lands in every suite at once. Helpers that only make sense next to one
particular group of tests stay in that file.
"""

from __future__ import annotations

from flappy_bird import settings
from flappy_bird.game import Game
from flappy_bird.pipe import Pipe

#: One frame of game time. Every suite steps the game in these increments.
DT = 1 / 60


def advance(game: Game, seconds: float, dt: float = DT, render: bool = False) -> None:
    """Step the game for ``seconds`` of game time, keeping the bird alive.

    Flapping only when the bird sinks below its start height holds a steady
    altitude, so the run never ends on game over and the pipe system keeps
    advancing.
    """
    for _ in range(round(seconds / dt)):
        if game.player.y > settings.BIRD_START_Y:
            game.flap()
        game.update(dt)
        if render:
            game.render()


def add_passed_pipe(game: Game) -> Pipe:
    """Put a pipe behind the bird, so the next update scores it."""
    pipe = Pipe(x=0, gap_y=settings.BIRD_START_Y)
    game.pipe_manager.pipes.append(pipe)
    return pipe


def crash(game: Game) -> None:
    """Force an immediate collision on the next update."""
    game.pipe_manager.pipes.append(
        Pipe(
            x=settings.BIRD_START_X - 10,
            gap_y=settings.BIRD_START_Y - settings.PIPE_GAP_SIZE,
        )
    )
    game.update(DT)
