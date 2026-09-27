"""Sanity checks for settings, window configuration, player physics and input."""

import random

import pygame
import pytest

from flappy_bird import settings
from flappy_bird.collision import check_any_pipe_collision, check_pipe_collision
from flappy_bird.game import Game
from flappy_bird.pipe import Pipe
from flappy_bird.pipe_manager import PipeManager
from flappy_bird.player import Player
from flappy_bird.scoring import count_newly_passed
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
        assert settings.PIPE_GAP_SIZE > 0
        assert settings.PIPE_SPAWN_INTERVAL > 0

    def test_gap_centers_are_configured_sensibly(self):
        assert (
            settings.PIPE_MIN_GAP_CENTER
            <= settings.PIPE_MAX_GAP_CENTER
            < settings.GROUND_TOP
        )
        half_gap = settings.PIPE_GAP_SIZE // 2
        assert settings.PIPE_MIN_GAP_CENTER - half_gap >= settings.CEILING_Y
        assert settings.PIPE_MAX_GAP_CENTER + half_gap <= settings.GROUND_TOP

    def test_pipe_spacing_leaves_a_reachable_gap(self):
        spacing = settings.PIPE_SPAWN_INTERVAL * settings.PIPE_SPEED
        assert spacing > settings.PIPE_GAP_SIZE


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
    def test_initial_state(self):
        pipe = Pipe(x=400, gap_y=350)
        assert pipe.x == 400.0
        assert pipe.gap_y == 350
        assert pipe.width == settings.PIPE_WIDTH
        assert pipe.gap == settings.PIPE_GAP_SIZE
        assert pipe.speed == settings.PIPE_SPEED
        assert pipe.is_off_screen is False

    def test_top_rect_spans_ceiling_to_gap(self):
        pipe = Pipe(x=100, gap_y=350)
        top = pipe.top_rect
        assert top.topleft == (100, settings.CEILING_Y)
        assert top.width == settings.PIPE_WIDTH
        assert top.bottom == pipe.gap_top

    def test_bottom_rect_spans_gap_to_ground(self):
        pipe = Pipe(x=100, gap_y=350)
        bottom = pipe.bottom_rect
        assert bottom.topleft == (100, pipe.gap_bottom)
        assert bottom.width == settings.PIPE_WIDTH
        assert bottom.bottom == settings.GROUND_TOP

    def test_gap_matches_configured_size(self):
        pipe = Pipe(x=100, gap_y=350)
        top, bottom = pipe.rects
        assert top.height + settings.PIPE_GAP_SIZE + bottom.height == (
            settings.GROUND_TOP - settings.CEILING_Y
        )
        assert bottom.top == top.bottom + settings.PIPE_GAP_SIZE

    def test_gap_stays_inside_playable_area_at_extremes(self):
        for center in (settings.PIPE_MIN_GAP_CENTER, settings.PIPE_MAX_GAP_CENTER):
            pipe = Pipe(x=100, gap_y=center)
            top, bottom = pipe.rects
            assert top.height > 0
            assert bottom.height > 0

    def test_moves_left_with_dt(self):
        pipe = Pipe(x=400, gap_y=350)
        pipe.update(0.5)
        assert pipe.x == pytest.approx(400 - settings.PIPE_SPEED * 0.5)

    def test_movement_is_frame_rate_independent(self):
        coarse = Pipe(x=400, gap_y=350)
        fine = Pipe(x=400, gap_y=350)
        for _ in range(30):
            coarse.update(1 / 30)
        for _ in range(120):
            fine.update(1 / 120)
        assert fine.x == pytest.approx(coarse.x, rel=1e-9)

    def test_off_screen_detection(self):
        pipe = Pipe(x=0, gap_y=350)
        assert pipe.is_off_screen is False
        pipe.x = -settings.PIPE_WIDTH
        assert pipe.is_off_screen is True

    def test_has_behind(self):
        pipe = Pipe(x=200, gap_y=350)
        assert pipe.has_behind(100) is False
        assert pipe.has_behind(200 + settings.PIPE_WIDTH + 1) is True


class TestPipeManager:
    def test_initial_state(self):
        manager = PipeManager()
        assert manager.pipes == []
        assert len(manager) == 0
        assert manager.elapsed == 0.0
        assert manager.spawn_interval == settings.PIPE_SPAWN_INTERVAL

    def test_rejects_non_positive_interval(self):
        with pytest.raises(ValueError):
            PipeManager(spawn_interval=0)

    def test_no_spawn_before_interval_elapses(self):
        manager = PipeManager()
        manager.update(1.0)
        assert manager.pipes == []
        assert manager.next_spawn_in == pytest.approx(0.6)

    def test_spawns_after_interval(self):
        manager = PipeManager()
        manager.update(1.0)
        manager.update(0.7)
        assert len(manager.pipes) == 1
        assert manager.elapsed == pytest.approx(0.1)

    def test_pipe_is_created_at_the_right_edge(self):
        manager = PipeManager()
        pipe = manager.spawn()
        assert pipe.x == settings.SCREEN_WIDTH
        assert pipe.speed == settings.PIPE_SPEED
        assert pipe.gap == settings.PIPE_GAP_SIZE
        assert manager.pipes == [pipe]

    def test_spawned_gap_is_within_configured_limits(self):
        manager = PipeManager(rng=random.Random(7))
        for _ in range(200):
            center = manager.spawn().gap_y
            assert settings.PIPE_MIN_GAP_CENTER <= center
            assert center <= settings.PIPE_MAX_GAP_CENTER

    def test_random_gap_center_is_randomised(self):
        rng = random.Random(1234)
        centers = {
            random_gap_center(min_center=100, max_center=600, rng=rng)
            for _ in range(50)
        }
        assert len(centers) > 10

    def test_random_gap_center_never_leaves_playable_area(self):
        rng = random.Random(99)
        half_gap = settings.PIPE_GAP_SIZE // 2
        for _ in range(200):
            center = random_gap_center(rng=rng)
            assert center - half_gap >= settings.CEILING_Y
            assert center + half_gap <= settings.GROUND_TOP

    def test_random_gap_center_rejects_impossible_ranges(self):
        with pytest.raises(ValueError):
            random_gap_center(min_center=650, max_center=660)

    def test_multiple_pipes_coexist(self):
        manager = PipeManager()
        for _ in range(100):
            manager.update(0.1)
        assert len(manager.pipes) >= 2
        assert len({id(pipe) for pipe in manager.pipes}) == len(manager.pipes)

    def test_pipes_move_left(self):
        manager = PipeManager()
        manager.spawn()
        pipe = manager.pipes[0]
        start_x = pipe.x
        manager.update(0.1)
        assert pipe.x == pytest.approx(start_x - settings.PIPE_SPEED * 0.1)

    def test_spawning_is_frame_rate_independent(self):
        coarse = PipeManager()
        fine = PipeManager()
        for _ in range(120):
            coarse.update(1 / 30)
        for _ in range(480):
            fine.update(1 / 120)
        assert len(coarse.pipes) == len(fine.pipes) == 2
        # Spawns land on a frame boundary, so positions may differ by the
        # distance covered in one coarse frame.
        assert [pipe.x for pipe in coarse.pipes] == pytest.approx(
            [pipe.x for pipe in fine.pipes], abs=settings.PIPE_SPEED / 30
        )

    def test_off_screen_pipes_are_removed(self):
        manager = PipeManager()
        pipe = manager.spawn()
        pipe.x = -settings.PIPE_WIDTH
        manager.update(0.016)
        assert manager.pipes == []

    def test_large_dt_does_not_flood_the_screen(self):
        manager = PipeManager()
        spawned = manager.update(30.0)
        assert spawned == PipeManager.MAX_SPAWNS_PER_UPDATE
        assert len(manager.pipes) == PipeManager.MAX_SPAWNS_PER_UPDATE

    def test_large_dt_does_not_run_the_timer_away(self):
        manager = PipeManager()
        manager.update(30.0)
        assert manager.elapsed < manager.spawn_interval

    def test_large_dt_keeps_spawning_predictable(self):
        first = PipeManager(rng=random.Random(3))
        second = PipeManager(rng=random.Random(3))
        first.update(30.0)
        second.update(30.0)
        assert [pipe.gap_y for pipe in first.pipes] == [
            pipe.gap_y for pipe in second.pipes
        ]

    def test_reset_clears_pipes_and_timer(self):
        manager = PipeManager()
        for _ in range(100):
            manager.update(0.1)
        assert manager.pipes
        manager.reset()
        assert manager.pipes == []
        assert manager.elapsed == 0.0
        assert manager.next_spawn_in == manager.spawn_interval


class TestGamePipes:
    def test_game_spawns_pipes_over_time(self, game):
        advance(game, 2.0)
        assert len(game.pipes) >= 1
        assert all(isinstance(pipe, Pipe) for pipe in game.pipes)

    def test_game_pipes_move_left(self, game):
        advance(game, 1.8)
        first = game.pipes[0]
        start_x = first.x
        advance(game, 0.2)
        assert first.x < start_x

    def test_spawned_pipes_sit_inside_the_playable_area(self, game):
        advance(game, 4.0)
        for pipe in game.pipes:
            top, bottom = pipe.rects
            assert top.height > 0
            assert bottom.bottom <= settings.GROUND_TOP

    def test_restart_clears_pipes_and_timer(self, game):
        advance(game, 2.0)
        assert game.pipes
        game.restart()
        assert game.pipes == []
        assert game.pipe_manager.elapsed == 0.0
        assert game.player.position == (
            settings.BIRD_START_X,
            settings.BIRD_START_Y,
        )

    def test_rendering_with_pipes_does_not_raise(self, game):
        advance(game, 2.5, render=True)
        assert game.pipes


class TestCollision:
    """Rect.colliderect semantics: only a positive overlap on both axes collides."""

    @pytest.fixture()
    def pipe(self):
        return Pipe(x=200, gap_y=300)

    @pytest.fixture()
    def half(self):
        return settings.BIRD_SIZE // 2

    def place_bird(self, x: int, y: int) -> Player:
        player = Player()
        player.x = float(x)
        player.y = float(y)
        return player

    def test_empty_pipe_list_has_no_collision(self):
        player = self.place_bird(230, 100)
        assert check_any_pipe_collision(player, []) is False

    def test_bird_completely_inside_the_gap_does_not_collide(self, pipe):
        assert check_pipe_collision(self.place_bird(230, pipe.gap_y), pipe) is False

    def test_bird_exactly_filling_the_gap_does_not_collide(self, pipe, half):
        just_below_top = pipe.gap_top + half + 1
        just_above_bottom = pipe.gap_bottom - half - 1
        for center in (just_below_top, just_above_bottom):
            assert check_pipe_collision(self.place_bird(230, center), pipe) is False

    def test_bird_flush_against_the_top_pipe_does_not_collide(self, pipe, half):
        flush = pipe.gap_top + half
        assert check_pipe_collision(self.place_bird(230, flush), pipe) is False

    def test_bird_flush_against_the_bottom_pipe_does_not_collide(self, pipe, half):
        flush = pipe.gap_bottom - half
        assert check_pipe_collision(self.place_bird(230, flush), pipe) is False

    def test_bird_one_pixel_into_the_top_pipe_collides(self, pipe, half):
        poking = pipe.gap_top - 1 + half
        assert check_pipe_collision(self.place_bird(230, poking), pipe) is True

    def test_bird_one_pixel_into_the_bottom_pipe_collides(self, pipe, half):
        poking = pipe.gap_bottom + 1 - half
        assert check_pipe_collision(self.place_bird(230, poking), pipe) is True

    def test_bird_deeply_overlapping_the_top_pipe_collides(self, pipe):
        assert check_pipe_collision(self.place_bird(230, 100), pipe) is True

    def test_bird_deeply_overlapping_the_bottom_pipe_collides(self, pipe):
        assert check_pipe_collision(self.place_bird(230, 500), pipe) is True

    def test_bird_above_the_gap_but_horizontally_clear_does_not_collide(
        self, pipe, half
    ):
        clear = pipe.x - half - 1
        assert check_pipe_collision(self.place_bird(clear, 100), pipe) is False

    def test_bird_past_the_pipe_does_not_collide(self, pipe, half):
        clear = pipe.x + pipe.width + half + 1
        assert check_pipe_collision(self.place_bird(clear, 100), pipe) is False

    def test_bird_touching_the_pipe_side_does_not_collide(self, pipe, half):
        flush = pipe.x - half
        assert check_pipe_collision(self.place_bird(flush, 100), pipe) is False

    def test_horizontal_overlap_inside_the_gap_does_not_collide(self, pipe):
        assert check_pipe_collision(self.place_bird(230, pipe.gap_y), pipe) is False

    def test_collision_uses_the_player_hitbox(self, pipe):
        player = self.place_bird(230, pipe.gap_y)
        assert check_pipe_collision(player, pipe) is False
        player.y = 100.0
        assert check_pipe_collision(player, pipe) is True

    def test_collision_detected_in_any_pipe_of_a_list(self, pipe):
        safe = Pipe(x=200, gap_y=300)
        deadly = Pipe(x=400, gap_y=100)
        player = self.place_bird(430, 400)
        assert check_any_pipe_collision(player, [safe, deadly]) is True

    def test_no_collision_when_every_pipe_is_safe(self, pipe):
        safe = [Pipe(x=200, gap_y=300), Pipe(x=400, gap_y=300)]
        player = self.place_bird(230, 300)
        assert check_any_pipe_collision(player, safe) is False

    def test_collision_ignores_degenerate_zero_height_columns(self):
        flat = Pipe(x=200, gap_y=settings.CEILING_Y)
        assert flat.top_rect.height == 0
        player = self.place_bird(230, 500)
        assert check_pipe_collision(player, flat) is True


class TestGameCollision:
    def place_blocking_pipe(self, game: Game) -> Pipe:
        """Add a pipe whose gap sits far above the bird, blocking its path."""
        pipe = Pipe(
            x=settings.BIRD_START_X - 10,
            gap_y=settings.BIRD_START_Y - settings.PIPE_GAP_SIZE,
        )
        game.pipe_manager.pipes.append(pipe)
        return pipe

    def test_pipe_collision_latches_game_over(self, game):
        self.place_blocking_pipe(game)
        game.update(DT)
        assert game.game_over is True

    def test_movement_freezes_after_collision(self, game):
        self.place_blocking_pipe(game)
        game.update(DT)
        assert game.game_over is True
        bird_y = game.player.y
        pipe_x = game.pipes[0].x
        for _ in range(10):
            game.update(DT)
        assert game.player.y == bird_y
        assert game.pipes[0].x == pipe_x

    def test_clear_path_keeps_the_game_running(self, game):
        game.pipe_manager.pipes.append(
            Pipe(x=settings.BIRD_START_X - 10, gap_y=settings.BIRD_START_Y)
        )
        game.update(DT)
        assert game.game_over is False

    def test_ground_collision_still_latches(self, game):
        game.player.y = settings.GROUND_TOP
        game.update(DT)
        assert game.game_over is True

    def test_ceiling_collision_still_latches(self, game):
        game.player.y = settings.CEILING_Y
        game.update(DT)
        assert game.game_over is True

    def test_restart_clears_collision_state(self, game):
        self.place_blocking_pipe(game)
        game.update(DT)
        assert game.game_over is True

        game.restart()
        assert game.game_over is False
        assert game.pipes == []
        assert game.player.position == (
            settings.BIRD_START_X,
            settings.BIRD_START_Y,
        )

        start_y = game.player.y
        game.update(DT)
        assert game.player.y != start_y

    def test_flapping_is_ignored_after_game_over(self, game):
        self.place_blocking_pipe(game)
        game.update(DT)
        frozen_velocity = game.player.velocity_y
        game.flap()
        assert game.player.velocity_y == frozen_velocity


class TestScoring:
    """One point per pipe pair, awarded only after it is fully behind."""

    def passed_pipe(self, x: int = 0, gap_y: int = 300) -> Pipe:
        """A pipe sitting completely behind the bird's start column."""
        return Pipe(x=x, gap_y=gap_y)

    def upcoming_pipe(self, gap_y: int = 300) -> Pipe:
        return Pipe(x=settings.SCREEN_WIDTH, gap_y=gap_y)

    def test_pipe_starts_unscored(self):
        assert self.passed_pipe().scored is False

    def test_no_pipes_awards_nothing(self):
        player = Player()
        assert count_newly_passed(player, []) == 0

    def test_bird_behind_a_pipe_awards_one_point(self):
        player = Player()
        assert count_newly_passed(player, [self.passed_pipe()]) == 1

    def test_same_pipe_cannot_award_twice(self):
        player = Player()
        pipe = self.passed_pipe()
        assert count_newly_passed(player, [pipe]) == 1
        assert count_newly_passed(player, [pipe]) == 0
        assert count_newly_passed(player, [pipe]) == 0

    def test_pipe_ahead_of_the_bird_awards_nothing(self):
        player = Player()
        assert count_newly_passed(player, [self.upcoming_pipe()]) == 0

    def test_bird_aligned_with_the_gap_awards_nothing(self):
        player = Player()
        overlapping = Pipe(x=settings.BIRD_START_X, gap_y=settings.BIRD_START_Y)
        assert count_newly_passed(player, [overlapping]) == 0

    def test_bird_flush_with_the_pipe_awards_nothing(self):
        player = Player()
        flush = Pipe(
            x=settings.BIRD_START_X + player.radius + settings.PIPE_WIDTH,
            gap_y=settings.BIRD_START_Y,
        )
        assert count_newly_passed(player, [flush]) == 0

    def test_multiple_pipes_award_multiple_points(self):
        player = Player()
        pipes = [self.passed_pipe(x=0), self.passed_pipe(x=-20), self.passed_pipe()]
        assert count_newly_passed(player, pipes) == 3

    def test_only_the_newly_passed_pipes_are_counted(self):
        player = Player()
        behind = self.passed_pipe()
        count_newly_passed(player, [behind])
        mixed = [behind, self.upcoming_pipe(), self.passed_pipe(x=-80)]
        assert count_newly_passed(player, mixed) == 1

    def test_pipes_at_the_same_position_are_scored_independently(self):
        player = Player()
        pipes = [self.passed_pipe(), self.passed_pipe(), self.passed_pipe()]
        assert count_newly_passed(player, pipes) == 3
        assert all(pipe.scored for pipe in pipes)

    def test_scoring_follows_pipes_as_they_move(self):
        player = Player()
        pipe = self.upcoming_pipe()
        steps = 0
        while not pipe.has_behind(player.x):
            pipe.update(1 / 60)
            steps += 1
            if not pipe.has_behind(player.x):
                assert count_newly_passed(player, [pipe]) == 0
        assert steps > 0
        assert count_newly_passed(player, [pipe]) == 1

    def test_removed_pipe_does_not_disturb_a_new_one(self):
        player = Player()
        old = self.passed_pipe()
        assert count_newly_passed(player, [old]) == 1
        assert count_newly_passed(player, []) == 0
        fresh = self.passed_pipe()
        assert fresh.scored is False
        assert count_newly_passed(player, [fresh]) == 1


class TestHighScore:
    def award(self, game: Game, points: int) -> None:
        game.add_score(points)

    def test_scores_start_at_zero(self, game):
        assert game.score == 0
        assert game.high_score == 0

    def test_high_score_follows_a_new_best(self, game):
        self.award(game, 3)
        assert game.score == 3
        assert game.high_score == 3

    def test_high_score_tracks_the_peak(self, game):
        self.award(game, 5)
        assert game.high_score == 5

    def test_lower_score_does_not_overwrite_high_score(self, game):
        self.award(game, 5)
        game.restart()
        self.award(game, 2)
        assert game.score == 2
        assert game.high_score == 5

    def test_restart_keeps_the_high_score_and_resets_the_score(self, game):
        self.award(game, 4)
        game.restart()
        assert game.score == 0
        assert game.high_score == 4

    def test_equal_score_keeps_the_high_score(self, game):
        self.award(game, 3)
        game.restart()
        self.award(game, 3)
        assert game.high_score == 3

    def test_awarding_zero_changes_nothing(self, game):
        self.award(game, 2)
        self.award(game, 0)
        assert game.score == 2
        assert game.high_score == 2

    def test_new_game_instance_starts_at_zero(self, game):
        self.award(game, 6)
        fresh = Game(headless=True)
        try:
            assert fresh.score == 0
            assert fresh.high_score == 0
        finally:
            pygame.quit()


class TestGameScoring:
    def add_passed_pipe(self, game: Game) -> Pipe:
        pipe = Pipe(x=0, gap_y=settings.BIRD_START_Y)
        game.pipe_manager.pipes.append(pipe)
        return pipe

    def test_score_and_high_score_start_at_zero(self, game):
        assert game.score == 0
        assert game.high_score == 0

    def test_passing_one_pipe_scores_one_point(self, game):
        self.add_passed_pipe(game)
        game.update(DT)
        assert game.score == 1
        assert game.high_score == 1

    def test_score_does_not_grow_every_frame(self, game):
        self.add_passed_pipe(game)
        game.update(DT)
        for _ in range(30):
            game.update(DT)
        assert game.score == 1

    def test_each_of_three_pipes_scores_once(self, game):
        for _ in range(3):
            self.add_passed_pipe(game)
        game.update(DT)
        assert game.score == 3
        for _ in range(5):
            game.update(DT)
        assert game.score == 3

    def test_pipes_ahead_of_the_bird_do_not_score(self, game):
        game.pipe_manager.pipes.append(
            Pipe(x=settings.SCREEN_WIDTH, gap_y=settings.BIRD_START_Y)
        )
        for _ in range(10):
            game.update(DT)
        assert game.score == 0

    def test_score_freezes_after_game_over(self, game):
        self.add_passed_pipe(game)
        game.game_over = True
        for _ in range(20):
            game.update(DT)
        assert game.score == 0

    def test_collision_does_not_award_a_point(self, game):
        pipe = Pipe(
            x=settings.BIRD_START_X - 10,
            gap_y=settings.BIRD_START_Y - settings.PIPE_GAP_SIZE,
        )
        game.pipe_manager.pipes.append(pipe)
        game.update(DT)
        assert game.game_over is True
        assert game.score == 0
        assert game.high_score == 0

    def test_crash_frame_after_passing_keeps_no_point(self, game):
        behind = Pipe(x=0, gap_y=settings.BIRD_START_Y)
        deadly = Pipe(
            x=settings.BIRD_START_X - 10,
            gap_y=settings.BIRD_START_Y - settings.PIPE_GAP_SIZE,
        )
        game.pipe_manager.pipes.extend([behind, deadly])
        game.update(DT)
        assert game.game_over is True
        assert game.score == 0

    def test_high_score_survives_a_full_round(self, game):
        for _ in range(3):
            self.add_passed_pipe(game)
        game.update(DT)
        assert game.high_score == 3

        game.game_over = True
        for _ in range(20):
            game.update(DT)
        assert game.score == 3
        assert game.high_score == 3

    def test_restart_clears_scoring_state(self, game):
        pipe = self.add_passed_pipe(game)
        game.update(DT)
        assert game.score == 1
        assert pipe.scored is True

        game.restart()
        assert game.score == 0
        assert game.high_score == 1
        assert game.pipes == []

        fresh = self.add_passed_pipe(game)
        assert fresh.scored is False
        game.update(DT)
        assert game.score == 1

    def test_score_keeps_climbing_across_a_long_run(self, game):
        # Gaps fixed on the bird's flight band so a long run survives and
        # every pipe that reaches the bird is passed.
        game.pipe_manager = PipeManager(
            spawn_interval=0.5,
            min_gap_center=250,
            max_gap_center=250,
            rng=random.Random(1),
        )
        advance(game, 10.0)
        assert game.game_over is False
        # A pipe needs (400 - 30) / 120 = 3.083s to travel behind the bird, so
        # the pipes spawned at 0.5s .. 6.5s are the 13 that score by t=10s.
        assert game.score == 13
        assert game.high_score == 13


class TestScoreRendering:
    def snapshot(self, game: Game) -> bytes:
        game.render()
        return pygame.image.tostring(game.screen, "RGB")

    def test_score_renders_in_headless_mode(self, game):
        assert self.snapshot(game)

    def test_changing_the_score_changes_the_screen(self, game):
        before = self.snapshot(game)
        game.score = 1234
        assert self.snapshot(game) != before

    def test_game_over_renders_score_and_best(self, game):
        game.score = 7
        game.high_score = 42
        game.game_over = True
        assert self.snapshot(game)

    def test_best_line_reflects_the_high_score(self, game):
        game.game_over = True
        game.score = 7
        game.high_score = 42
        with_best = self.snapshot(game)
        game.high_score = 99
        assert self.snapshot(game) != with_best

    def test_best_is_hidden_during_play(self, game):
        game.high_score = 42
        playing = self.snapshot(game)
        game.game_over = True
        assert self.snapshot(game) != playing


def test_clamp_bounds_values():
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(11, 0, 10) == 10
