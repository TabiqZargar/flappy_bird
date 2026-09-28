"""Console entry point: ``flappy-bird`` and ``python -m flappy_bird``.

Both routes call the same :meth:`~flappy_bird.game.Game.run` the repository's
``main.py`` does, so there is exactly one way to start a round and no game logic
lives in the launcher.
"""

from __future__ import annotations

from .game import Game


def main() -> None:
    """Open the window and run until it is closed."""
    Game().run()


if __name__ == "__main__":
    main()
