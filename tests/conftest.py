"""Fixtures shared by more than one test module.

``test_audio.py`` keeps its own ``game``/``idle_game`` fixtures: they look
similar but swap in a recording stand-in for the audio manager, which is the
whole point of that file.
"""

import pygame
import pytest

from flappy_bird.game import Game


@pytest.fixture()
def game():
    """A game with a round already under way.

    The physics, pipe, collision and scoring tests all drive a live round, so
    the fixture starts one; the start-screen behaviour gets its own fixture.
    """
    instance = Game(headless=True)
    instance.start_round()
    pygame.event.clear()
    yield instance
    pygame.quit()


@pytest.fixture()
def idle_game():
    """A freshly constructed game, still waiting in the START state."""
    instance = Game(headless=True)
    pygame.event.clear()
    yield instance
    pygame.quit()
