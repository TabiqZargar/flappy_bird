"""Flappy Bird - a small Pygame clone built on a modular scaffold."""

from . import settings
from .collision import check_any_pipe_collision, check_pipe_collision
from .game import Game
from .pipe import Pipe
from .pipe_manager import PipeManager
from .player import Player
from .utils import clamp, centered_rect, frame_delta, random_gap_center

__all__ = [
    "Game",
    "Pipe",
    "PipeManager",
    "Player",
    "check_any_pipe_collision",
    "check_pipe_collision",
    "settings",
    "clamp",
    "centered_rect",
    "frame_delta",
    "random_gap_center",
]

__version__ = "0.1.0"
