"""Tests for the progressive difficulty ladder and its wiring into the game.

The ladder itself is a pure function of the score, so most of this file is plain
arithmetic: boundaries, monotonicity and the clamps. The rest drives a live game
to prove the plumbing -- score to profile, profile to new pipes, and *never* to
pipes already in flight.
"""

import ast
import dataclasses
import random

import pygame
import pytest

from flappy_bird import settings
from flappy_bird.difficulty import (
    BASELINE,
    MAXIMUM,
    DifficultyProfile,
    all_profiles,
    difficulty_level,
    get_difficulty,
    profile_for_level,
)
from flappy_bird.game import Game
from flappy_bird.pipe_manager import PipeManager
from flappy_bird.state import GameState
from tests.helpers import DT, add_passed_pipe, advance, crash

PROFILES = all_profiles()
TOP = settings.DIFFICULTY_MAX_LEVEL


# --- Configuration ----------------------------------------------------------


class TestDifficultySettings:
    def test_the_ladder_has_at_least_one_step(self):
        assert settings.DIFFICULTY_MAX_LEVEL >= 1
        assert settings.DIFFICULTY_SCORE_STEP > 0

    def test_each_step_actually_changes_something(self):
        assert settings.DIFFICULTY_SPEED_INCREMENT > 0
        assert settings.DIFFICULTY_GAP_DECREMENT > 0
        assert settings.DIFFICULTY_SPAWN_DECREMENT > 0

    def test_the_bounds_leave_the_baseline_outside_them(self):
        assert settings.DIFFICULTY_MAX_SPEED > settings.PIPE_SPEED
        assert settings.DIFFICULTY_MIN_GAP < settings.PIPE_GAP_SIZE
        assert settings.DIFFICULTY_MIN_SPAWN_INTERVAL < settings.PIPE_SPAWN_INTERVAL

    def test_the_bounds_are_sane_in_themselves(self):
        assert settings.DIFFICULTY_MIN_GAP > 0
        assert settings.DIFFICULTY_MAX_SPEED > 0
        assert settings.DIFFICULTY_MIN_SPAWN_INTERVAL > 0

    def test_the_hardest_gap_still_leaves_room_for_the_bird(self):
        assert settings.DIFFICULTY_MIN_GAP > settings.BIRD_SIZE

    def test_the_baseline_pipe_constants_are_untouched(self):
        # Level 0 has to be exactly the baseline the difficulty ladder derives
        # from: 120 px/s, a 160 px gap, and a pipe every 2.0s.
        assert settings.PIPE_SPEED == 120
        assert settings.PIPE_GAP_SIZE == 160
        assert settings.PIPE_SPAWN_INTERVAL == 2.0


# --- The pure ladder --------------------------------------------------------


class TestDifficultyLevel:
    def test_score_zero_is_level_zero(self):
        assert difficulty_level(0) == 0

    def test_score_below_the_first_step_stays_at_baseline(self):
        assert difficulty_level(settings.DIFFICULTY_SCORE_STEP - 1) == 0

    def test_the_step_boundary_is_exact(self):
        assert difficulty_level(settings.DIFFICULTY_SCORE_STEP) == 1

    def test_levels_start_exactly_on_the_boundaries(self):
        for level in range(1, TOP + 1):
            score = level * settings.DIFFICULTY_SCORE_STEP
            assert difficulty_level(score) == level

    def test_one_point_below_a_boundary_is_the_previous_level(self):
        for level in range(1, TOP + 1):
            score = level * settings.DIFFICULTY_SCORE_STEP
            assert difficulty_level(score - 1) == level - 1

    def test_a_negative_score_is_treated_as_baseline(self):
        assert difficulty_level(-1) == 0
        assert difficulty_level(-50) == 0

    def test_a_huge_score_is_capped(self):
        assert difficulty_level(10_000) == TOP

    def test_the_level_is_always_a_valid_index(self):
        for score in (-1000, -1, 0, 1, 7, 24, 25, 100, 10**9):
            assert 0 <= difficulty_level(score) <= TOP


class TestGetDifficulty:
    def test_score_zero_returns_the_baseline(self):
        assert get_difficulty(0) == BASELINE

    def test_the_baseline_is_the_original_pipe_setup(self):
        profile = get_difficulty(0)
        assert profile.pipe_speed == settings.PIPE_SPEED
        assert profile.pipe_gap == settings.PIPE_GAP_SIZE
        assert profile.spawn_interval == settings.PIPE_SPAWN_INTERVAL

    def test_negative_scores_return_the_baseline(self):
        assert get_difficulty(-1) == BASELINE
        assert get_difficulty(-999) == BASELINE

    def test_the_profile_reports_its_own_level(self):
        for score in (0, 3, 9, 14, 22, 40):
            assert get_difficulty(score).level == difficulty_level(score)

    def test_the_maximum_is_reached_at_the_last_step(self):
        score = TOP * settings.DIFFICULTY_SCORE_STEP
        assert get_difficulty(score) == MAXIMUM

    def test_the_maximum_is_not_exceeded(self):
        assert get_difficulty(10_000) == MAXIMUM

    def test_the_maximum_is_reached_exactly_on_the_last_step(self):
        # The cap belongs to the level, so the very point that completes the last
        # step is the first one that counts as maximum.
        step = settings.DIFFICULTY_SCORE_STEP
        assert get_difficulty(TOP * step - 1) == profile_for_level(TOP - 1)
        assert get_difficulty(TOP * step) == MAXIMUM

    def test_the_same_score_always_gives_the_identical_profile(self):
        first = get_difficulty(17)
        for _ in range(50):
            assert get_difficulty(17) is first

    def test_scores_inside_a_level_share_one_profile(self):
        step = settings.DIFFICULTY_SCORE_STEP
        assert get_difficulty(step) is get_difficulty(step * 2 - 1)

    def test_the_gap_stays_a_whole_number_of_pixels(self):
        for profile in PROFILES:
            assert isinstance(profile.pipe_gap, int)

    def test_a_float_score_is_handled_like_the_truncated_value(self):
        assert get_difficulty(7.9) == get_difficulty(7)


class TestProfileForLevel:
    def test_it_matches_the_level_from_a_score(self):
        for level in range(TOP + 1):
            score = level * settings.DIFFICULTY_SCORE_STEP
            assert profile_for_level(level) is get_difficulty(score)

    def test_a_negative_level_clamps_to_baseline(self):
        assert profile_for_level(-5) == BASELINE

    def test_a_level_above_the_cap_clamps_to_the_maximum(self):
        assert profile_for_level(TOP + 50) == MAXIMUM


class TestProfilesAreBounded:
    def test_there_is_exactly_one_profile_per_level(self):
        assert len(PROFILES) == TOP + 1
        assert [p.level for p in PROFILES] == list(range(TOP + 1))

    def test_speed_never_exceeds_the_maximum(self):
        for profile in PROFILES:
            assert profile.pipe_speed <= settings.DIFFICULTY_MAX_SPEED

    def test_the_gap_never_falls_below_the_minimum(self):
        for profile in PROFILES:
            assert profile.pipe_gap >= settings.DIFFICULTY_MIN_GAP

    def test_the_spawn_interval_never_falls_below_the_minimum(self):
        for profile in PROFILES:
            assert profile.spawn_interval >= settings.DIFFICULTY_MIN_SPAWN_INTERVAL

    def test_nothing_is_negative_or_empty(self):
        for profile in PROFILES:
            assert profile.pipe_speed > 0
            assert profile.pipe_gap > 0
            assert profile.spawn_interval > 0

    def test_every_gap_is_reachable_at_every_level(self):
        # Consecutive pairs must stay further apart than the gap is wide, or the
        # bird would be asked to thread two openings that overlap on screen.
        for profile in PROFILES:
            assert profile.spacing > profile.pipe_gap

    def test_every_gap_fits_between_the_ceiling_and_the_ground(self):
        for profile in PROFILES:
            assert profile.pipe_gap <= settings.GROUND_TOP - settings.CEILING_Y

    def test_profiles_are_immutable(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            PROFILES[0].pipe_gap = 1  # type: ignore[misc]

    def test_profiles_compare_by_value(self):
        assert DifficultyProfile(0, 120.0, 160, 2.0) == BASELINE


class TestProgressionIsMonotonic:
    def test_the_level_never_goes_backwards(self):
        scores = list(range(0, TOP * settings.DIFFICULTY_SCORE_STEP + 3))
        levels = [difficulty_level(score) for score in scores]
        assert levels == sorted(levels)

    def test_speed_only_ever_increases(self):
        speeds = [profile.pipe_speed for profile in PROFILES]
        assert speeds == sorted(speeds)

    def test_the_gap_only_ever_shrinks(self):
        gaps = [profile.pipe_gap for profile in PROFILES]
        assert gaps == sorted(gaps, reverse=True)

    def test_the_spawn_interval_only_ever_shrinks(self):
        intervals = [profile.spawn_interval for profile in PROFILES]
        assert intervals == sorted(intervals, reverse=True)

    def test_every_level_differs_from_the_one_before(self):
        # Each level is paired with the next one, so the tail is one shorter.
        for previous, current in zip(PROFILES, PROFILES[1:], strict=False):
            assert (current.pipe_speed, current.pipe_gap, current.spawn_interval) != (
                previous.pipe_speed,
                previous.pipe_gap,
                previous.spawn_interval,
            )

    def test_only_the_final_level_is_flagged_as_maximum(self):
        assert [p.is_maximum for p in PROFILES] == [False] * TOP + [True]

    def test_scoring_past_the_cap_never_hardens_the_game(self):
        step = settings.DIFFICULTY_SCORE_STEP
        cap = TOP * step
        for score in range(cap, cap + 50 * step):
            assert get_difficulty(score) == MAXIMUM

    def test_the_progression_is_deterministic(self):
        scores = list(range(0, 60))
        first = [get_difficulty(score) for score in scores]
        second = [get_difficulty(score) for score in scores]
        assert first == second
        assert len(set(first)) == TOP + 1


class TestProgressionIsSubtle:
    def test_the_hardest_level_is_not_extreme(self):
        assert MAXIMUM.pipe_speed <= settings.PIPE_SPEED * 1.4
        assert MAXIMUM.pipe_gap >= settings.PIPE_GAP_SIZE * 0.7
        assert MAXIMUM.spawn_interval >= settings.PIPE_SPAWN_INTERVAL * 0.7

    def test_a_casual_run_never_reaches_the_hardest_level(self):
        # Most players die well before the cap; the ladder has to be felt, not hit.
        assert TOP * settings.DIFFICULTY_SCORE_STEP >= 20

    def test_the_hardest_gap_is_still_several_birds_wide(self):
        assert MAXIMUM.pipe_gap >= settings.BIRD_SIZE * 3

    def test_difficulty_does_not_touch_the_bird(self):
        # The bird's feel is the one thing difficulty must never change.
        for name in ("GRAVITY", "JUMP_VELOCITY", "MAX_FALL_SPEED", "BIRD_SIZE"):
            value = getattr(settings, name)
            assert isinstance(value, (int, float))
            assert value != 0


# --- PipeManager plumbing ---------------------------------------------------


class TestPipeManagerDifficulty:
    def test_a_fresh_manager_starts_at_the_baseline(self):
        manager = PipeManager()
        assert manager.difficulty == BASELINE
        assert manager.speed == settings.PIPE_SPEED
        assert manager.gap == settings.PIPE_GAP_SIZE
        assert manager.spawn_interval == settings.PIPE_SPAWN_INTERVAL

    def test_a_fresh_manager_is_not_pinned(self):
        assert PipeManager().is_pinned is False

    def test_a_new_profile_changes_the_next_pipe(self):
        manager = PipeManager()
        manager.set_difficulty(MAXIMUM)
        pipe = manager.spawn()
        assert pipe.speed == MAXIMUM.pipe_speed
        assert pipe.gap == MAXIMUM.pipe_gap

    def test_a_new_profile_changes_the_spawn_interval(self):
        manager = PipeManager()
        manager.set_difficulty(MAXIMUM)
        assert manager.spawn_interval == pytest.approx(MAXIMUM.spawn_interval)

    def test_an_explicit_interval_pins_the_whole_manager(self):
        manager = PipeManager(spawn_interval=0.5)
        assert manager.is_pinned is True
        manager.set_difficulty(MAXIMUM)
        assert manager.spawn_interval == 0.5
        assert manager.speed == settings.PIPE_SPEED
        assert manager.gap == settings.PIPE_GAP_SIZE

    def test_an_explicit_speed_pins_the_whole_manager(self):
        manager = PipeManager(speed=90.0)
        manager.set_difficulty(MAXIMUM)
        assert manager.speed == 90.0
        assert manager.spawn_interval == settings.PIPE_SPAWN_INTERVAL

    def test_an_explicit_gap_pins_the_whole_manager(self):
        manager = PipeManager(gap=150)
        manager.set_difficulty(MAXIMUM)
        assert manager.gap == 150
        assert manager.speed == settings.PIPE_SPEED

    def test_pinned_values_still_spawn_usable_pipes(self):
        manager = PipeManager(spawn_interval=0.5, gap=150, rng=random.Random(1))
        for _ in range(50):
            pipe = manager.spawn()
            assert pipe.gap == 150
            assert pipe.speed == settings.PIPE_SPEED

    def test_the_spawned_gap_always_fits_the_playable_area(self):
        manager = PipeManager(rng=random.Random(4))
        for profile in PROFILES:
            manager.set_difficulty(profile)
            for _ in range(20):
                pipe = manager.spawn()
                assert pipe.gap_top >= settings.CEILING_Y
                assert pipe.gap_bottom <= settings.GROUND_TOP

    def test_reset_returns_to_the_baseline(self):
        manager = PipeManager()
        manager.set_difficulty(MAXIMUM)
        manager.spawn()
        manager.reset()
        assert manager.difficulty == BASELINE
        assert manager.speed == settings.PIPE_SPEED
        assert manager.gap == settings.PIPE_GAP_SIZE
        assert manager.spawn_interval == settings.PIPE_SPAWN_INTERVAL

    def test_the_values_can_still_be_overridden_after_construction(self):
        manager = PipeManager()
        manager.spawn_interval = 2.0
        manager.speed = 100.0
        manager.gap = 155
        assert manager.spawn_interval == 2.0
        assert manager.speed == 100.0
        assert manager.gap == 155

    def test_setting_a_nonsense_value_is_refused(self):
        manager = PipeManager()
        for name in ("spawn_interval", "speed", "gap"):
            with pytest.raises(ValueError):
                setattr(manager, name, 0)
            with pytest.raises(ValueError):
                setattr(manager, name, -5)


class TestPipesInFlightAreUntouched:
    def test_a_pipe_keeps_its_speed_for_its_whole_life(self):
        manager = PipeManager()
        pipe = manager.spawn()
        assert pipe.speed == settings.PIPE_SPEED
        manager.set_difficulty(MAXIMUM)
        for _ in range(30):
            manager.update(DT)
        assert pipe.speed == settings.PIPE_SPEED

    def test_a_pipe_keeps_its_gap_for_its_whole_life(self):
        manager = PipeManager()
        pipe = manager.spawn()
        gap = pipe.gap
        manager.set_difficulty(MAXIMUM)
        for _ in range(30):
            manager.update(DT)
        assert pipe.gap == gap
        assert pipe.gap_top == pipe.gap_y - gap // 2
        assert pipe.gap_bottom == pipe.gap_y + gap // 2

    def test_a_pipe_does_not_speed_up_mid_flight(self):
        manager = PipeManager()
        pipe = manager.spawn()
        before = pipe.x
        manager.set_difficulty(MAXIMUM)
        manager.update(0.1)
        # One 0.1s step at the *old* speed, not the new one.
        assert before - pipe.x == pytest.approx(settings.PIPE_SPEED * 0.1)

    def test_pipes_spawned_after_the_change_use_the_new_profile(self):
        manager = PipeManager(rng=random.Random(2))
        old = manager.spawn()
        manager.set_difficulty(MAXIMUM)
        new = manager.spawn()
        assert old.speed == settings.PIPE_SPEED
        assert old.gap == settings.PIPE_GAP_SIZE
        assert new.speed == MAXIMUM.pipe_speed
        assert new.gap == MAXIMUM.pipe_gap

    def test_the_shrinking_interval_actually_spawns_earlier(self):
        fast = PipeManager()
        fast.set_difficulty(MAXIMUM)
        assert fast.spawn_due(MAXIMUM.spawn_interval - 0.01) == 0
        assert fast.spawn_due(0.02) == 1

    def test_large_dt_is_still_capped_at_the_hardest_level(self):
        manager = PipeManager()
        manager.set_difficulty(MAXIMUM)
        spawned = manager.update(30.0)
        assert spawned == PipeManager.MAX_SPAWNS_PER_UPDATE
        assert len(manager.pipes) == PipeManager.MAX_SPAWNS_PER_UPDATE
        assert manager.elapsed < manager.spawn_interval

    def test_large_dt_leaves_no_spawn_debt_behind(self):
        manager = PipeManager()
        manager.set_difficulty(MAXIMUM)
        manager.update(30.0)
        # The leftover time is discarded, so the next spawn is a full interval
        # away rather than a burst of catch-up pipes.
        assert manager.next_spawn_in == pytest.approx(MAXIMUM.spawn_interval)

    def test_a_huge_difficulty_jump_does_not_flood_the_screen(self):
        manager = PipeManager()
        for profile in PROFILES:
            manager.set_difficulty(profile)
        assert manager.update(5.0) <= PipeManager.MAX_SPAWNS_PER_UPDATE
        assert len(manager.pipes) <= PipeManager.MAX_SPAWNS_PER_UPDATE


# --- Game integration -------------------------------------------------------


class TestGameDifficulty:
    def test_a_new_game_starts_at_the_baseline(self, idle_game):
        assert idle_game.difficulty == BASELINE

    def test_start_uses_the_baseline(self, idle_game):
        assert idle_game.difficulty.level == 0
        assert idle_game.pipe_manager.speed == settings.PIPE_SPEED

    def test_score_zero_produces_baseline_pipes(self, game):
        assert game.score == 0
        assert game.difficulty == BASELINE
        advance(game, 2.0)
        assert all(pipe.speed == settings.PIPE_SPEED for pipe in game.pipes)
        assert all(pipe.gap == settings.PIPE_GAP_SIZE for pipe in game.pipes)

    def test_the_game_exposes_the_profile_it_is_using(self, game):
        assert game.difficulty is game.pipe_manager.difficulty

    def test_scoring_raises_the_difficulty(self, game):
        add_passed_pipe(game)
        game.update(DT)
        assert game.score == 1
        assert game.difficulty == BASELINE

    def test_a_whole_step_raises_the_difficulty(self, game):
        game.add_score(settings.DIFFICULTY_SCORE_STEP)
        game.sync_difficulty()
        assert game.difficulty.level == 1
        assert game.difficulty.pipe_speed > settings.PIPE_SPEED

    def test_scoring_changes_the_parameters_for_future_pipes(self, game):
        early = game.pipe_manager.spawn()
        step = settings.DIFFICULTY_SCORE_STEP
        game.add_score(step)
        game.sync_difficulty()
        late = game.pipe_manager.spawn()
        assert late.speed == pytest.approx(get_difficulty(step).pipe_speed)
        assert late.speed > early.speed

    def test_a_point_does_not_reshape_the_pipe_that_paid_it(self, game):
        pipe = add_passed_pipe(game)
        shape = (pipe.gap, pipe.speed, pipe.gap_y, pipe.gap_top, pipe.gap_bottom)
        heights = (pipe.top_rect.height, pipe.bottom_rect.height)
        game.update(DT)
        assert game.score == 1
        # The pipe scrolls on, but its opening is exactly the same opening.
        opening = (pipe.gap, pipe.speed, pipe.gap_y, pipe.gap_top, pipe.gap_bottom)
        assert opening == shape
        assert (pipe.top_rect.height, pipe.bottom_rect.height) == heights

    def test_existing_pipes_keep_their_geometry_as_difficulty_rises(self, game):
        early = game.pipe_manager.spawn()
        before = (early.gap, early.speed, early.gap_y)
        for _ in range(1, TOP * settings.DIFFICULTY_SCORE_STEP + 1):
            game.add_score(1)
            game.sync_difficulty()
            game.update(DT)
        assert (early.gap, early.speed, early.gap_y) == before

    def test_existing_pipes_do_not_suddenly_change_speed(self, game):
        pipe = game.pipe_manager.spawn()
        speed = pipe.speed
        for _ in range(120):
            game.add_score(1)
            game.sync_difficulty()
            game.update(DT)
        assert pipe.speed == speed

    def test_new_pipes_use_the_current_difficulty(self, game):
        game.add_score(TOP * settings.DIFFICULTY_SCORE_STEP)
        game.sync_difficulty()
        pipe = game.pipe_manager.spawn()
        assert pipe.speed == pytest.approx(MAXIMUM.pipe_speed)
        assert pipe.gap == MAXIMUM.pipe_gap

    def test_the_game_never_exceeds_the_maximum(self, game):
        game.add_score(10_000)
        game.sync_difficulty()
        assert game.difficulty == MAXIMUM
        game.update(DT)
        assert game.difficulty == MAXIMUM
        assert game.pipe_manager.speed <= settings.DIFFICULTY_MAX_SPEED

    def test_scoring_far_past_the_cap_keeps_the_cap(self, game):
        for _ in range(30):
            add_passed_pipe(game)
            game.update(DT)
        assert game.score >= TOP * settings.DIFFICULTY_SCORE_STEP
        assert game.difficulty == MAXIMUM

    def test_a_collision_does_not_raise_the_difficulty(self, game):
        crash(game)
        assert game.state is GameState.GAME_OVER
        assert game.difficulty == BASELINE

    def test_game_over_freezes_the_difficulty(self, game):
        game.add_score(20)
        game.sync_difficulty()
        frozen = game.difficulty
        crash(game)
        for _ in range(60):
            game.update(DT)
        assert game.state is GameState.GAME_OVER
        assert game.difficulty == frozen

    def test_the_start_screen_never_hardens(self, idle_game):
        idle_game.add_score(50)
        for _ in range(60):
            idle_game.update(DT)
        assert idle_game.state is GameState.START
        assert idle_game.difficulty == BASELINE
        assert idle_game.pipes == []

    def test_attract_screen_pipes_stay_at_the_baseline(self, idle_game):
        for _ in range(300):
            idle_game.update(DT)
        assert all(pipe.speed == settings.PIPE_SPEED for pipe in idle_game.pipes)

    def test_restart_returns_to_the_baseline(self, game):
        game.add_score(TOP * settings.DIFFICULTY_SCORE_STEP)
        game.sync_difficulty()
        assert game.difficulty == MAXIMUM
        game.restart()
        assert game.difficulty == BASELINE
        assert game.pipe_manager.speed == settings.PIPE_SPEED
        assert game.pipe_manager.gap == settings.PIPE_GAP_SIZE
        assert game.pipe_manager.spawn_interval == settings.PIPE_SPAWN_INTERVAL

    def test_restart_clears_the_pipes_and_the_spawn_timer(self, game):
        advance(game, 2.0)
        game.add_score(20)
        game.sync_difficulty()
        game.restart()
        assert game.pipes == []
        assert game.pipe_manager.elapsed == 0.0
        assert game.score == 0

    def test_pipes_after_a_restart_are_baseline_pipes(self, game):
        game.add_score(50)
        game.sync_difficulty()
        game.restart()
        pipe = game.pipe_manager.spawn()
        assert pipe.speed == settings.PIPE_SPEED
        assert pipe.gap == settings.PIPE_GAP_SIZE

    def test_the_high_score_survives_a_restart(self, game):
        game.add_score(12)
        game.restart()
        assert game.score == 0
        assert game.high_score == 12
        assert game.difficulty == BASELINE

    def test_the_high_score_survives_several_hard_rounds(self, game):
        game.add_score(40)
        game.sync_difficulty()
        game.restart()
        game.add_score(10)
        game.sync_difficulty()
        game.restart()
        assert game.high_score == 40
        assert game.difficulty == BASELINE

    def test_large_dt_still_respects_the_spawn_safety_limit(self, game):
        spawned = game.pipe_manager.update(30.0)
        assert spawned <= PipeManager.MAX_SPAWNS_PER_UPDATE
        assert len(game.pipes) <= PipeManager.MAX_SPAWNS_PER_UPDATE

    def test_a_long_stall_does_not_explode_into_pipes(self, game):
        for _ in range(10):
            game.update(30.0)
        assert len(game.pipes) <= PipeManager.MAX_SPAWNS_PER_UPDATE * 2

    def test_difficulty_survives_a_stall_without_debt(self, game):
        game.add_score(TOP * settings.DIFFICULTY_SCORE_STEP)
        game.sync_difficulty()
        game.pipe_manager.update(30.0)
        assert game.pipe_manager.elapsed < game.pipe_manager.spawn_interval

    def test_the_bird_is_untouched_by_difficulty(self, game):
        feel = (settings.GRAVITY, settings.JUMP_VELOCITY, settings.MAX_FALL_SPEED)
        game.add_score(50)
        game.sync_difficulty()
        game.player.jump()
        game.update(DT)
        assert (
            settings.GRAVITY,
            settings.JUMP_VELOCITY,
            settings.MAX_FALL_SPEED,
        ) == feel

    def test_the_same_score_produces_the_same_fall(self, game):
        hard = Game(headless=True)
        try:
            hard.add_score(12)
            hard.sync_difficulty()
            game.add_score(12)
            game.sync_difficulty()
            assert game.difficulty == hard.difficulty
            assert game.player.position == hard.player.position
            assert game.player.velocity_y == hard.player.velocity_y
        finally:
            pygame.quit()

    def test_deterministic_runs_produce_identical_progression(self):
        runs = []
        for seed in range(2):
            run = Game(headless=True)
            try:
                run.pipe_manager.rng = random.Random(seed)
                run.start_round()
                seen = []
                for _ in range(12):
                    pipe = add_passed_pipe(run)
                    run.update(DT)
                    seen.append((run.difficulty.level, pipe.speed, pipe.gap))
                runs.append(seen)
            finally:
                pygame.quit()
        assert runs[0] == runs[1]
        levels = [level for level, _, _ in runs[0]]
        assert levels == sorted(levels)
        assert levels[-1] > levels[0]

    def test_progression_actually_appears_over_a_long_run(self, game):
        seen = {game.difficulty.level}
        for _ in range(20):
            add_passed_pipe(game)
            game.update(DT)
            seen.add(game.difficulty.level)
        assert max(seen) > min(seen)


class TestDifficultyIsIsolated:
    """Difficulty must not leak into the modules it is not allowed to touch.

    These read the *code* rather than the file text, so a module is free to talk
    about the score in a docstring without looking like a violation.
    """

    ISOLATED = ("player", "collision", "scoring", "visuals", "audio")
    SCORE_FREE = ("difficulty", "pipe_manager")

    def source(self, name: str) -> str:
        from pathlib import Path

        return (Path(settings.__file__).parent / f"{name}.py").read_text(
            encoding="utf-8"
        )

    def tree(self, name: str) -> ast.Module:
        return ast.parse(self.source(name))

    def imported_modules(self, name: str) -> set[str]:
        found: set[str] = set()
        for node in ast.walk(self.tree(name)):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    found.add(node.module.lstrip("."))
                # `from . import settings` names the module on the alias.
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
        return found

    def attribute_names(self, name: str) -> set[str]:
        return {
            node.attr
            for node in ast.walk(self.tree(name))
            if isinstance(node, ast.Attribute)
        }

    def names(self, name: str) -> set[str]:
        return {
            node.id for node in ast.walk(self.tree(name)) if isinstance(node, ast.Name)
        }

    def test_the_isolated_modules_do_not_import_difficulty(self):
        for module in self.ISOLATED:
            assert "difficulty" not in self.imported_modules(module), module

    def test_the_isolated_modules_never_ask_for_a_profile(self):
        for module in self.ISOLATED:
            found = self.names(module) | self.attribute_names(module)
            assert "get_difficulty" not in found, module
            assert "difficulty_level" not in found, module
            assert "DifficultyProfile" not in found, module

    def test_the_isolated_modules_never_read_a_difficulty_setting(self):
        for module in self.ISOLATED:
            assert not any(
                name.startswith("DIFFICULTY_") for name in self.names(module)
            ), module

    def test_difficulty_only_imports_settings(self):
        # ``from __future__``, the dataclass machinery, and its own settings.
        # Nothing else: no pygame, no pipes, no game.
        assert self.imported_modules("difficulty") == {
            "__future__",
            "annotations",
            "dataclasses",
            "dataclass",
            "settings",
        }

    def test_difficulty_never_reaches_outside_itself(self):
        found = self.names("difficulty") | self.attribute_names("difficulty")
        for forbidden in (
            "Game",
            "Pipe",
            "PipeManager",
            "Player",
            "Visuals",
            "AudioManager",
            "pygame",
            "random",
            "update",
            "spawn",
            "draw",
        ):
            assert forbidden not in found, forbidden

    def test_difficulty_defines_no_behaviour(self):
        # Four pure lookups plus the two read-only properties on the profile.
        # No update/spawn/draw/reset anywhere, by design.
        functions = {
            node.name
            for node in ast.walk(self.tree("difficulty"))
            if isinstance(node, ast.FunctionDef)
        }
        assert functions == {
            "difficulty_level",
            "get_difficulty",
            "profile_for_level",
            "all_profiles",
            "_build_profiles",
            "spacing",
            "is_maximum",
        }
        for verb in ("update", "spawn", "draw", "reset", "step", "move"):
            assert verb not in functions

    def test_difficulty_holds_no_mutable_state(self):
        # A frozen dataclass plus a module-level tuple: nothing to reset, nothing
        # that could make two calls disagree.
        classes = [
            node
            for node in ast.walk(self.tree("difficulty"))
            if isinstance(node, ast.ClassDef)
        ]
        assert [node.name for node in classes] == ["DifficultyProfile"]
        decorators = [
            decorator for node in classes for decorator in node.decorator_list
        ]
        assert any(
            isinstance(d, ast.Call)
            and getattr(d.func, "id", "") == "dataclass"
            and any(kw.arg == "frozen" and kw.value.value is True for kw in d.keywords)
            for d in decorators
        )
        assigned = {
            target.id
            for node in self.tree("difficulty").body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            if isinstance(target, ast.Name)
        }
        assert assigned == {"_PROFILES", "BASELINE", "MAXIMUM"}

    def test_the_pipe_manager_does_not_know_the_score(self):
        assert "score" not in self.attribute_names("pipe_manager")
        assert "score" not in self.names("pipe_manager")
        assert "scoring" not in self.imported_modules("pipe_manager")
        assert "game" not in self.imported_modules("pipe_manager")

    def test_only_the_game_and_the_pipe_manager_import_the_ladder(self):
        talking = {
            module
            for module in (
                "game",
                "pipe_manager",
                "difficulty",
                "player",
                "collision",
                "scoring",
                "visuals",
                "audio",
                "state",
                "utils",
                "pipe",
            )
            if "difficulty" in self.imported_modules(module)
        }
        assert talking == {"game", "pipe_manager"}

    def test_the_ladder_is_a_pure_call(self):
        # No RNG, no clock, no environment: same input, same output object.
        for module in ("random", "time", "os", "datetime"):
            assert module not in self.imported_modules("difficulty")
        assert get_difficulty(13) is get_difficulty(13)
        # 13 and 14 sit in the same level, 15 opens the next one.
        assert get_difficulty(13) is get_difficulty(14)
        assert get_difficulty(14) is not get_difficulty(15)


class TestDifficultyIndicator:
    def test_the_level_is_shown_while_playing(self, game):
        game.add_score(10)
        game.sync_difficulty()
        game.render()
        assert pygame.image.tostring(game.screen, "RGB")

    def test_rendering_every_level_is_safe(self, game):
        for profile in PROFILES:
            game.pipe_manager.set_difficulty(profile)
            game.render()
        assert pygame.image.tostring(game.screen, "RGB")

    def test_the_indicator_costs_a_bounded_number_of_cached_strings(self, game):
        # Holding the score still and sweeping every level isolates the
        # indicator: the score string is constant, so only the level varies.
        game.visuals.text.clear()
        for profile in PROFILES:
            game.pipe_manager.set_difficulty(profile)
            game.render()
        assert len(game.visuals.text) <= TOP + 2

    def test_the_indicator_never_renegotiates_a_cached_string(self, game):
        game.pipe_manager.set_difficulty(MAXIMUM)
        game.render()
        first = len(game.visuals.text)
        for _ in range(50):
            game.render()
        assert len(game.visuals.text) == first

    def test_the_indicator_is_hidden_outside_play(self, idle_game):
        idle_game.render()
        idle_game.game_over = True
        idle_game.render()
        assert pygame.image.tostring(idle_game.screen, "RGB")
