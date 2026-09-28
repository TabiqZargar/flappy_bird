"""Entry point: ``python main.py`` from the repository root.

Run ``python -m pip install -e .`` once first, which is what puts ``flappy_bird``
on the import path. Everything else lives in the package.
"""

from flappy_bird import Game

if __name__ == "__main__":
    Game().run()
