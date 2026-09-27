"""Sanity checks for settings, window configuration, player physics and input."""

import pygame
import pytest

from flappy_bird import settings
from flappy_bird.game import Game
from flappy_bird.pipe import Pipe
from flappy_bird.player import Player
from flappy_bird.utils import clamp, random_gap_center

DT = 1 / 60


@pytest.fixture()
def game():
    instance = Game(headless=True)
    pygame.event.clear()
    yield instance
    pygame.quit()


def post_event(event_type: int, **attributes) -> None:
    pygame.event.post(pygame.event.Event(event_type, attributes))


def simulate(seconds: float, dt: float) -> Player:
    """Run a player for ``seconds`` of game time in ``dt`` steps."""
    player = Player()
    for _ in range(round(seconds / dt)):
        player.update(dt)
    return player


class TestSettings:
    def test_screen_size_is_400x700(self):
        assert settings.SCREEN_WIDTH == 400
        assert settings.SCREEN_HEIGHT == 700

    def test_fps_and_physics_are_positive(self):
        assert settings.FPS > 0
        assert settings.GRAVITY > 0
        assert settings.MAX_FALL_SPEED > 0

    def test_jump_velocity_points_upwards(self):
        assert settings.JUMP_VELOCITY < 0

    def test_bird_size_is_configured(self):
        assert settings.BIRD_SIZE > 0
        assert settings.BIRD_SIZE <= min(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)

    def test_bird_starts_inside_playable_area(self):
        assert 0 < settings.BIRD_START_X < settings.SCREEN_WIDTH
        assert settings.CEILING_Y < settings.BIRD_START_Y < settings.GROUND_TOP

    def test_playable_area_is_consistent(self):
        assert 0 < settings.GROUND_HEIGHT < settings.SCREEN_HEIGHT
        assert settings.GROUND_TOP == settings.SCREEN_HEIGHT - settings.GROUND_HEIGHT
        assert settings.GROUND_TOP > settings.CEILING_Y

    def test_pipe_gap_leaves_room_for_pipes(self):
        assert settings.PIPE_WIDTH > 0
        assert settings.PIPE_SPEED > 0
        assert settings.PIPE_GAP + 2 * settings.PIPE_MIN_EDGE <= settings.SCREEN_HEIGHT


class TestPlayerPhysics:
    def test_initial_position(self):
        player = Player()
        assert player.x == float(settings.BIRD_START_X)
        assert player.y == float(settings.BIRD_START_Y)
        assert player.position == (settings.BIRD_START_X, settings.BIRD_START_Y)
        assert player.velocity_y == 0.0

    def test_position_is_kept_as_floats(self):
        player = Player()
        player.update(DT)
        assert isinstance(player.x, float)
        assert isinstance(player.y, float)

    def test_gravity_increases_downward_velocity(self):
        player = Player()
        player.update(DT)
        assert player.velocity_y == pytest.approx(settings.GRAVITY * DT)
        assert player.velocity_y > 0

    def test_gravity_accumulates_over_frames(self):
        player = Player()
        for _ in range(10):
            player.update(DT)
        assert player.velocity_y == pytest.approx(settings.GRAVITY * 10 * DT)

    def test_jump_sets_upward_velocity(self):
        player = Player()
        player.jump()
        assert player.velocity_y == settings.JUMP_VELOCITY
        assert player.velocity_y < 0

    def test_jump_moves_the_bird_upwards(self):
        player = Player()
        start_y = player.y
        player.jump()
        player.update(DT)
        assert player.y < start_y

    def test_repeated_jumps_do_not_accumulate_velocity(self):
        player = Player()
        for _ in range(5):
            player.jump()
            player.update(DT)
        assert player.velocity_y == pytest.approx(
            settings.JUMP_VELOCITY + settings.GRAVITY * DT
        )

    def test_maximum_fall_speed_is_respected(self):
        player = Player()
        for _ in range(600):
            player.update(DT)
        assert player.velocity_y == settings.MAX_FALL_SPEED

    def test_velocity_is_frame_rate_independent(self):
        coarse = simulate(0.5, 1 / 30)
        fine = simulate(0.5, 1 / 120)
        assert coarse.velocity_y == pytest.approx(
            settings.GRAVITY * 0.5, rel=1e-6
        )
        assert fine.velocity_y == pytest.approx(coarse.velocity_y, rel=1e-6)

    def test_displacement_is_frame_rate_independent(self):
        coarse = simulate(0.5, 1 / 30)
        fine = simulate(0.5, 1 / 120)
        assert fine.y == pytest.approx(coarse.y, rel=0.02)

    def test_displacement_matches_kinematic_expectation(self):
        elapsed = 0.5
        expected = settings.GRAVITY * elapsed**2 / 2 + settings.BIRD_START_Y
        assert simulate(elapsed, 1 / 120).y == pytest.approx(expected, rel=0.01)

    def test_reset_restores_start_position(self):
        player = Player()
        player.jump()
        for _ in range(30):
            player.update(DT)
        player.reset()
        assert player.position == (settings.BIRD_START_X, settings.BIRD_START_Y)
        assert player.velocity_y == 0.0

    def test_rect_tracks_the_floating_point_position(self):
        player = Player()
        assert player.rect.size == (settings.BIRD_SIZE, settings.BIRD_SIZE)
        assert player.rect.center == player.position


class TestPlayerBoundaries:
    def test_ceiling_detected_above_playable_area(self):
        player = Player(y=settings.BIRD_SIZE / 2 + 1)
        assert player.hit_ceiling is False
        player.y -= 1
        assert player.hit_ceiling is True

    def test_ground_detected_when_reaching_ground(self):
        player = Player(y=settings.GROUND_TOP - settings.BIRD_SIZE)
        assert player.hit_ground is False
        player.y = settings.GROUND_TOP - settings.BIRD_SIZE / 2
        assert player.hit_ground is True

    def test_bird_in_middle_is_inside_bounds(self):
        player = Player()
        assert player.hit_ceiling is False
        assert player.hit_ground is False
        assert player.is_out_of_bounds is False

    def test_falling_onto_the_ground_is_detected(self):
        player = Player()
        for _ in range(600):
            player.update(DT)
        assert player.hit_ground is True
        assert player.bottom >= settings.GROUND_TOP


class TestGameInput:
    def test_space_triggers_jump(self, game):
        post_event(pygame.KEYDOWN, key=pygame.K_SPACE)
        game.handle_events()
        assert game.player.velocity_y == settings.JUMP_VELOCITY
        assert game.has_flapped is True

    def test_left_mouse_click_triggers_jump(self, game):
        post_event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10))
        game.handle_events()
        assert game.player.velocity_y == settings.JUMP_VELOCITY
        assert game.has_flapped is True

    def test_right_mouse_click_does_not_trigger_jump(self, game):
        post_event(pygame.MOUSEBUTTONDOWN, button=3, pos=(10, 10))
        game.handle_events()
        assert game.player.velocity_y == 0.0
        assert game.has_flapped is False

    def test_quit_event_stops_the_game(self, game):
        game.running = True
        post_event(pygame.QUIT)
        game.handle_events()
        assert game.running is False

    def test_escape_stops_the_game(self, game):
        game.running = True
        post_event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        game.handle_events()
        assert game.running is False

    def test_restart_resets_the_player(self, game):
        game.game_over = True
        game.score = 7
        post_event(pygame.KEYDOWN, key=pygame.K_SPACE)
        post_event(pygame.KEYDOWN, key=pygame.K_r)
        game.handle_events()
        assert game.game_over is False
        assert game.score == 0
        assert game.player.position == (settings.BIRD_START_X, settings.BIRD_START_Y)


class TestGameWindow:
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


class TestGameLoopIntegration:
    def test_bird_moves_vertically_across_frames(self, game):
        positions = []
        for _ in range(20):
            game.update(DT)
            positions.append(game.player.y)
        assert positions[-1] > positions[0]
        assert len(set(positions)) > 5

    def test_flapping_moves_the_bird_upwards(self, game):
        post_event(pygame.KEYDOWN, key=pygame.K_SPACE)
        game.handle_events()
        start_y = game.player.y
        for _ in range(5):
            game.update(DT)
        assert game.player.y < start_y

    def test_game_over_when_bird_reaches_ground(self, game):
        game.player.y = settings.GROUND_TOP - 1
        game.update(DT)
        assert game.player.hit_ground is True
        assert game.game_over is True

    def test_game_over_when_bird_hits_ceiling(self, game):
        game.player.y = 1
        game.update(DT)
        assert game.player.hit_ceiling is True
        assert game.game_over is True

    def test_frozen_after_game_over(self, game):
        game.game_over = True
        frozen_y = game.player.y
        game.update(DT)
        assert game.player.y == frozen_y


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
