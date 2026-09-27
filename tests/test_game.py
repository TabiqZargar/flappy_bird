"""Sanity checks for settings, window configuration and core entities."""

import pygame
import pytest

from flappy_bird import settings
from flappy_bird.game import Game
from flappy_bird.pipe import Pipe
from flappy_bird.player import Player
from flappy_bird.utils import clamp, random_gap_center


class TestSettings:
    def test_screen_size_is_400x700(self):
        assert settings.SCREEN_WIDTH == 400
        assert settings.SCREEN_HEIGHT == 700

    def test_fps_and_physics_are_positive(self):
        assert settings.FPS > 0
        assert settings.GRAVITY > 0
        assert settings.MAX_FALL_SPEED >= settings.GRAVITY * 0.01

    def test_bird_fits_on_screen(self):
        assert 0 < settings.BIRD_WIDTH <= settings.SCREEN_WIDTH
        assert 0 < settings.BIRD_HEIGHT <= settings.SCREEN_HEIGHT
        assert 0 <= settings.BIRD_START_X <= settings.SCREEN_WIDTH
        assert 0 <= settings.BIRD_START_Y <= settings.SCREEN_HEIGHT

    def test_pipe_gap_leaves_room_for_pipes(self):
        assert settings.PIPE_WIDTH > 0
        assert settings.PIPE_SPEED > 0
        minimum_edge = settings.PIPE_MIN_EDGE
        assert settings.PIPE_GAP + 2 * minimum_edge <= settings.SCREEN_HEIGHT


class TestGameWindow:
    @pytest.fixture()
    def game(self):
        instance = Game(headless=True)
        yield instance
        pygame.quit()

    def test_window_matches_settings(self, game):
        assert game.screen.get_size() == (
            settings.SCREEN_WIDTH,
            settings.SCREEN_HEIGHT,
        )

    def test_initial_state_is_valid(self, game):
        assert game.pipes == []
        assert game.score == 0
        assert game.game_over is False
        assert isinstance(game.player, Player)

    def test_runs_a_bounded_number_of_frames(self, game):
        game.run(max_frames=5)
        assert game.running is False


class TestPlayer:
    def test_falls_under_gravity(self):
        player = Player()
        start_y = player.y
        for _ in range(10):
            player.update(1 / 60)
        assert player.y > start_y

    def test_jump_moves_upwards(self):
        player = Player()
        player.jump()
        player.update(1 / 60)
        assert player.y < settings.BIRD_START_Y

    def test_reset_restores_start_position(self):
        player = Player()
        player.jump()
        player.update(0.5)
        player.reset()
        assert player.position == (settings.BIRD_START_X, settings.BIRD_START_Y)
        assert player.velocity_y == 0.0


class TestPipe:
    def test_gap_is_centred_and_moves_left(self):
        pipe = Pipe(x=settings.SCREEN_WIDTH, gap_y=350)
        top, bottom = pipe.rects
        assert top.height + settings.PIPE_GAP + bottom.height == settings.SCREEN_HEIGHT
        assert bottom.top == top.bottom + settings.PIPE_GAP

        start_x = pipe.x
        pipe.update(0.5)
        assert pipe.x == pytest.approx(start_x - settings.PIPE_SPEED * 0.5)

    def test_random_gap_center_stays_on_screen(self):
        for _ in range(50):
            center = random_gap_center()
            half_gap = settings.PIPE_GAP // 2
            assert settings.PIPE_MIN_EDGE <= center - half_gap
            assert center + half_gap <= settings.SCREEN_HEIGHT - settings.PIPE_MIN_EDGE


def test_clamp_bounds_values():
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(11, 0, 10) == 10
