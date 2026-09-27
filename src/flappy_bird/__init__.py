"""Flappy Bird - a small Pygame clone built on a modular scaffold."""

from . import settings
from .game import Game
from .pipe import Pipe
from .player import Player
from .utils import clamp, centered_rect, frame_delta, random_gap_center

__all__ = [
    "Game",
    "Pipe",
    "Player",
    "settings",
    "clamp",
    "centered_rect",
    "frame_delta",
    "random_gap_center",
]

__version__ = "0.1.0"
