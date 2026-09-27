"""Flappy Bird - a small Pygame clone built on a modular scaffold."""

from . import settings
from .audio import AudioManager, pre_init_mixer, render_buffers
from .collision import check_any_pipe_collision, check_pipe_collision
from .game import Game
from .pipe import Pipe
from .pipe_manager import PipeManager
from .player import Player
from .scoring import count_newly_passed
from .state import GameState
from .utils import clamp, centered_rect, frame_delta, random_gap_center
from .visuals import (
    BirdSprite,
    Cloud,
    CloudField,
    GroundBand,
    PanelCache,
    TextCache,
    Visuals,
    build_cloud,
    build_sky,
    draw_bird,
    tilt_for_velocity,
)

__all__ = [
    "AudioManager",
    "Game",
    "GameState",
    "Pipe",
    "PipeManager",
    "Player",
    "BirdSprite",
    "Cloud",
    "CloudField",
    "GroundBand",
    "PanelCache",
    "TextCache",
    "Visuals",
    "build_cloud",
    "build_sky",
    "check_any_pipe_collision",
    "check_pipe_collision",
    "count_newly_passed",
    "draw_bird",
    "pre_init_mixer",
    "render_buffers",
    "settings",
    "clamp",
    "centered_rect",
    "frame_delta",
    "random_gap_center",
    "tilt_for_velocity",
]

__version__ = "0.1.0"
