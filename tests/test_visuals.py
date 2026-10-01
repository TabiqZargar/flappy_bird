"""Tests for the presentation layer: sky, clouds, ground, bird and UI surfaces.

Everything here is decorative, so the recurring theme is that drawing must never
reach back into the simulation.
"""

import random

import pygame
import pytest

from flappy_bird import settings
from flappy_bird.pipe import Pipe
from flappy_bird.state import GameState
from flappy_bird.visuals import (
    BIRD_BODY_PIXELS,
    BIRD_HIGHLIGHT_COLOR,
    BIRD_PALETTE,
    BIRD_SHADOW_COLOR,
    BIRD_WING_PIXELS,
    CLOUD_PROFILE,
    DISTANT_PROFILES,
    BirdSprite,
    PanelCache,
    SceneryField,
    TextCache,
    Visuals,
    blend_color,
    build_cloud,
    build_sky,
    cloud_block_size,
    tilt_for_velocity,
)
from tests.helpers import DT


@pytest.fixture(autouse=True)
def pygame_ready():
    """Font and display modules are torn down by ``pygame.quit`` elsewhere."""
    pygame.init()
    yield


@pytest.fixture()
def surface():
    yield pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))


@pytest.fixture()
def visuals():
    yield Visuals(rng=random.Random(7))


def snapshot(target: pygame.Surface) -> bytes:
    return pygame.image.tostring(target, "RGB")


def cloud_at(visuals: Visuals, index: int = 0):
    """The nth cloud of the field, through the iterable interface."""
    return list(visuals.clouds)[index]


class TestSky:
    def test_builds_at_screen_size(self):
        sky = build_sky()
        assert sky.get_size() == (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)

    def test_gradient_runs_light_to_dark(self, surface):
        sky = build_sky()
        top = sky.get_at((10, 0))[:3]
        bottom = sky.get_at((10, settings.SCREEN_HEIGHT - 1))[:3]
        assert sum(top) < sum(bottom), "the sky should get lighter towards the ground"

    def test_gradient_is_horizontal_and_even(self, surface):
        sky = build_sky()
        for y in (0, 300, 600):
            left = sky.get_at((0, y))[:3]
            right = sky.get_at((settings.SCREEN_WIDTH - 1, y))[:3]
            assert left == right

    def test_sky_is_cached_after_first_use(self, visuals):
        assert visuals._sky is None
        first = visuals.sky
        assert visuals.sky is first

    def test_draw_sky_paints_the_gradient(self, visuals, surface):
        visuals.draw_sky(surface)
        assert snapshot(surface) != bytes(
            surface.get_width() * surface.get_height() * 3
        )

    def test_sky_covers_the_whole_screen_including_the_ground_band(
        self, visuals, surface
    ):
        visuals.draw_sky(surface)
        assert (
            surface.get_at((10, settings.SCREEN_HEIGHT - 1))[:3]
            == settings.SKY_BOTTOM_COLOR
        )
        assert (
            surface.get_at((10, settings.GROUND_TOP + 5))[:3]
            != settings.BACKGROUND_COLOR
        )


class TestClouds:
    def test_field_builds_the_configured_count(self, visuals):
        assert len(visuals.clouds) == settings.CLOUD_COUNT

    def test_clouds_have_images(self, visuals):
        for cloud in visuals.clouds:
            assert cloud.image.get_width() > 0
            assert cloud.image.get_height() > 0

    def test_layers_have_different_speeds(self, visuals):
        speeds = {cloud.speed for cloud in visuals.clouds}
        assert len(speeds) > 1, "parallax needs more than one drift speed"

    def test_nearer_layers_drift_faster(self, visuals):
        fast = max(visuals.clouds, key=lambda c: c.layer).speed
        slow = min(visuals.clouds, key=lambda c: c.layer).speed
        assert fast > slow

    def test_update_moves_clouds_left_by_speed_times_dt(self, visuals):
        cloud = cloud_at(visuals)
        start = cloud.x
        visuals.clouds.update(0.5)
        assert cloud.x == pytest.approx(start - cloud.speed * 0.5)

    def test_update_uses_dt(self, visuals):
        cloud = cloud_at(visuals)
        start = cloud.x
        visuals.clouds.update(0.25)
        half = start - cloud.x
        visuals.clouds.update(0.25)
        assert (start - cloud.x) == pytest.approx(half * 2)

    def test_zero_dt_moves_nothing(self, visuals):
        before = [cloud.x for cloud in visuals.clouds]
        visuals.clouds.update(0.0)
        assert [cloud.x for cloud in visuals.clouds] == before

    def test_clouds_recycle_when_leaving_the_left_edge(self, visuals):
        cloud = cloud_at(visuals)
        cloud.x = -cloud.width - 1
        assert cloud.is_off_screen is True
        visuals.clouds.update(1 / 60)
        assert cloud.is_off_screen is False
        assert cloud.x > 0, "a recycled cloud re-enters from the right"

    def test_recycled_cloud_keeps_its_appearance_and_speed(self, visuals):
        cloud = cloud_at(visuals)
        image, speed, layer = cloud.image, cloud.speed, cloud.layer
        cloud.x = -cloud.width - 10
        visuals.clouds.update(1 / 60)
        assert cloud.image is image
        assert cloud.speed == speed
        assert cloud.layer == layer

    def test_long_run_keeps_every_cloud_on_screen(self, visuals):
        for _ in range(3000):
            visuals.clouds.update(DT)
        for cloud in visuals.clouds:
            assert cloud.x > -cloud.width, "clouds must wrap, not escape"

    def test_draw_clouds_changes_the_screen(self, visuals, surface):
        before = snapshot(surface)
        visuals.draw_clouds(surface)
        assert snapshot(surface) != before

    def test_build_cloud_scales(self):
        small = build_cloud(0.5)
        large = build_cloud(1.5)
        assert large.get_width() > small.get_width()
        assert large.get_height() > small.get_height()

    def test_build_cloud_is_transparent_around_the_puffs(self):
        cloud = build_cloud(1.0)
        assert cloud.get_at((0, 0))[3] == 0


class TestGroundBand:
    def test_ground_top_matches_the_physics_line(self, visuals):
        assert visuals.ground.grass_top == settings.GROUND_TOP

    def test_offset_starts_at_zero(self, visuals):
        assert visuals.ground.offset == 0.0

    def test_update_scrolls_the_offset(self, visuals):
        visuals.ground.update(0.1)  # 12px, short of the 24px wrap
        assert visuals.ground.offset == pytest.approx(
            settings.GROUND_SCROLL_SPEED * 0.1
        )

    def test_offset_wraps_within_one_tile(self, visuals):
        tile = visuals.ground.tile_width
        for _ in range(1000):
            visuals.ground.update(DT)
            assert 0.0 <= visuals.ground.offset < tile

    def test_offset_wraps_exactly_at_the_tile_width(self, visuals):
        tile = visuals.ground.tile_width
        speed = settings.GROUND_SCROLL_SPEED
        visuals.ground.update(tile / speed)
        assert visuals.ground.offset == pytest.approx(0.0, abs=1e-9)

    def test_offset_never_changes_the_collision_line(self, visuals):
        for _ in range(200):
            visuals.ground.update(DT)
            assert visuals.ground.grass_top == settings.GROUND_TOP

    def test_ground_height_is_unchanged(self, visuals):
        assert visuals.ground._tile.get_height() == settings.GROUND_HEIGHT

    def test_ground_covers_the_whole_width(self, visuals, surface):
        visuals.ground.draw(surface)
        for x in (0, 1, 23, 24, 25, 199, 399):
            assert surface.get_at((x, settings.GROUND_TOP + 5))[:3] in (
                settings.GROUND_COLOR,
                settings.GROUND_SOIL_COLOR,
                settings.GROUND_SOIL_MARK_COLOR,
            )

    def test_grass_band_is_one_flat_colour(self, visuals, surface):
        visuals.ground.draw(surface)
        row = settings.GROUND_TOP + settings.GROUND_GRASS_HEIGHT - 1
        colors = {surface.get_at((x, row))[:3] for x in range(settings.SCREEN_WIDTH)}
        assert colors == {settings.GROUND_COLOR}

    def test_scrolling_changes_the_ground_pixels(self, visuals, surface):
        visuals.ground.draw(surface)
        before = snapshot(surface)
        visuals.ground.update(0.12)
        surface.fill((0, 0, 0))
        visuals.ground.draw(surface)
        assert snapshot(surface) != before

    def test_clear_offset_resets_the_scroll(self, visuals):
        visuals.ground.update(1.0)
        visuals.ground.clear_offset()
        assert visuals.ground.offset == 0.0


class TestBirdTilt:
    def test_rising_gives_a_nose_up_tilt(self):
        assert tilt_for_velocity(-400.0) > 0

    def test_falling_gives_a_nose_down_tilt(self):
        assert tilt_for_velocity(400.0) < 0

    def test_level_flight_is_level(self):
        assert tilt_for_velocity(0.0) == 0.0

    def test_clamped_at_the_nose_up_limit(self):
        assert tilt_for_velocity(-100_000.0) == settings.BIRD_TILT_MAX_DEGREES

    def test_clamped_at_the_nose_down_limit(self):
        assert tilt_for_velocity(100_000.0) == settings.BIRD_TILT_MIN_DEGREES

    def test_a_full_speed_flap_reaches_the_up_limit(self):
        assert tilt_for_velocity(settings.JUMP_VELOCITY) == (
            settings.BIRD_TILT_MAX_DEGREES
        )

    def test_terminal_fall_stays_inside_the_limits(self):
        tilt = tilt_for_velocity(settings.MAX_FALL_SPEED)
        assert settings.BIRD_TILT_MIN_DEGREES <= tilt < 0

    def test_tilt_index_is_always_in_range(self):
        sprite = BirdSprite()
        for velocity in (-10_000, -520, -1, 0, 1, 520, 10_000):
            assert 0 <= sprite.tilt_index(velocity) < sprite.tilt_steps

    def test_tilt_index_changes_with_velocity(self):
        sprite = BirdSprite()
        assert sprite.tilt_index(-600) > sprite.tilt_index(600)

    def test_cached_angles_sit_inside_the_limits(self):
        sprite = BirdSprite()
        for angle in sprite.cached_angles():
            assert (
                settings.BIRD_TILT_MIN_DEGREES
                <= angle
                <= (settings.BIRD_TILT_MAX_DEGREES)
            )

    def test_tilt_index_falls_as_the_bird_sinks(self):
        sprite = BirdSprite()
        indexes = [sprite.tilt_index(v) for v in range(-800, 801, 25)]
        assert indexes == sorted(indexes, reverse=True)


class TestBirdSprite:
    def test_update_advances_the_wing_phase(self):
        sprite = BirdSprite()
        sprite.update(0.5)
        assert sprite.wing_phase > 0.0

    def test_wing_animation_uses_dt(self):
        fast, slow = BirdSprite(), BirdSprite()
        fast.update(0.05)
        slow.update(0.01)
        assert fast.wing_phase > slow.wing_phase

    def test_wing_phase_wraps_at_one_beat(self):
        sprite = BirdSprite()
        sprite.update(10.0)
        assert 0.0 <= sprite.wing_phase < 1.0

    def test_zero_dt_leaves_the_phase_alone(self):
        sprite = BirdSprite()
        sprite.update(0.0)
        assert sprite.wing_phase == 0.0

    def test_wing_index_stays_in_range(self):
        sprite = BirdSprite()
        for _ in range(200):
            sprite.update(0.037)
            assert 0 <= sprite.wing_index < sprite.wing_frames

    def test_every_wing_frame_is_reachable(self):
        sprite = BirdSprite()
        seen = set()
        for _ in range(400):
            sprite.update(0.037)
            seen.add(sprite.wing_index)
        assert seen == set(range(sprite.wing_frames))

    def test_frames_are_cached_not_rebuilt(self):
        sprite = BirdSprite()
        first = sprite.frame(0.0)
        assert sprite.frame(0.0) is first

    def test_frame_cache_is_bounded(self):
        sprite = BirdSprite()
        for velocity in range(-800, 801, 20):
            sprite.frame(float(velocity))
        assert len(sprite) <= sprite.tilt_steps * sprite.wing_frames

    def test_different_velocities_give_different_poses(self):
        sprite = BirdSprite()
        sprite.wing_phase = 0.0
        assert sprite.frame(-600.0) is not sprite.frame(600.0)

    def test_sprite_is_about_the_bird_size(self):
        sprite = BirdSprite()
        frame = sprite.frame(0.0)
        assert frame.get_width() >= settings.BIRD_SIZE
        assert frame.get_width() < settings.BIRD_SIZE * 3

    def test_draw_paints_the_body_colour(self, surface):
        sprite = BirdSprite()
        sprite.draw(surface, 200, 300, 0.0)
        assert bytes(settings.BIRD_COLOR) in snapshot(surface)

    def test_draw_centres_the_sprite(self, surface):
        sprite = BirdSprite()
        sprite.draw(surface, 200, 300, 0.0)
        palette = {
            settings.BIRD_COLOR,
            settings.BIRD_BELLY_COLOR,
            settings.BIRD_WING_COLOR,
            settings.BIRD_WING_EDGE_COLOR,
            settings.BIRD_BEAK_COLOR,
            settings.BIRD_BEAK_DARK_COLOR,
            settings.BIRD_EYE_COLOR,
            settings.BIRD_EYE_PUPIL_COLOR,
            settings.BIRD_OUTLINE_COLOR,
        }
        assert surface.get_at((200, 300))[:3] in palette


def opaque_colours(sprite: pygame.Surface) -> set[tuple[int, int, int]]:
    """Every fully opaque colour in a sprite, ignoring the transparent canvas."""
    return {
        sprite.get_at((x, y))[:3]
        for y in range(sprite.get_height())
        for x in range(sprite.get_width())
        if sprite.get_at((x, y))[3] == 255
    }


class TestBirdIsPixelArt:
    """The sprite must read as hard-edged pixels, not as a smooth drawing."""

    def test_the_sprite_is_generated_not_loaded_from_disk(self):
        # No asset can be missing, misnamed or stale: every pixel comes from
        # the tables in visuals.py, so the bird is always drawable.
        assert settings.BIRD_LOGICAL_SIZE == len(BIRD_BODY_PIXELS)
        assert len(BIRD_WING_PIXELS) == settings.BIRD_WING_FRAMES
        assert BirdSprite().frame(0.0).get_width() > 0

    def test_every_authored_row_is_exactly_one_logical_pixel_wide(self):
        for row in BIRD_BODY_PIXELS:
            assert len(row) == settings.BIRD_LOGICAL_SIZE
        for pose in BIRD_WING_PIXELS:
            for row in pose:
                assert len(row) == len(pose[0])

    def test_the_art_only_uses_pixels_the_palette_defines(self):
        allowed = set(BIRD_PALETTE) | {"."}
        for row in BIRD_BODY_PIXELS:
            assert set(row) <= allowed
        for pose in BIRD_WING_PIXELS:
            for row in pose:
                assert set(row) <= allowed

    def test_the_art_is_as_wide_as_the_collision_box(self):
        # 17 authored pixels scaled by 2 is exactly BIRD_SIZE, so the drawing
        # lines up with the hitbox instead of floating inside it.
        assert settings.BIRD_LOGICAL_SIZE * settings.BIRD_PIXEL_SCALE == (
            settings.BIRD_SIZE
        )

    def test_the_scale_is_a_whole_number_of_pixels(self):
        # A fractional scale would resample the grid and blur it.
        assert settings.BIRD_PIXEL_SCALE >= 2
        assert isinstance(settings.BIRD_PIXEL_SCALE, int)
        assert settings.BIRD_SIZE % settings.BIRD_PIXEL_SCALE == 0

    def test_the_scale_factor_is_an_integer(self):
        sprite = BirdSprite()
        sprite.wing_phase = 0.0
        rotated = sprite.logical_frame(0)
        for velocity in (-800.0, -400.0, 0.0, 400.0, 800.0):
            frame = sprite.frame(velocity)
            angle = sprite.cached_angles()[sprite.tilt_index(velocity)]
            spun = pygame.transform.rotate(rotated, angle)
            assert frame.get_size() == (
                spun.get_width() * settings.BIRD_PIXEL_SCALE,
                spun.get_height() * settings.BIRD_PIXEL_SCALE,
            )

    def test_every_pixel_is_a_hard_square_block(self):
        # The real proof of nearest-neighbour scaling: uniform 2x2 blocks. A
        # smoothed sprite would blend neighbouring palette colours here.
        sprite = BirdSprite()
        sprite.wing_phase = 0.0
        frame = sprite.frame(0.0)
        scale = settings.BIRD_PIXEL_SCALE
        for y in range(0, frame.get_height() - 1, scale):
            for x in range(0, frame.get_width() - 1, scale):
                block = {
                    frame.get_at((x + dx, y + dy))[:3]
                    for dx in range(scale)
                    for dy in range(scale)
                }
                assert len(block) == 1, f"blended block at {(x, y)}"

    def test_no_pixel_is_antialiased_into_a_new_colour(self):
        sprite = BirdSprite()
        expected = {
            settings.BIRD_COLOR,
            settings.BIRD_OUTLINE_COLOR,
            settings.BIRD_BELLY_COLOR,
            settings.BIRD_WING_COLOR,
            settings.BIRD_WING_EDGE_COLOR,
            settings.BIRD_BEAK_COLOR,
            settings.BIRD_BEAK_DARK_COLOR,
            settings.BIRD_EYE_COLOR,
            settings.BIRD_EYE_PUPIL_COLOR,
            BIRD_HIGHLIGHT_COLOR,
            BIRD_SHADOW_COLOR,
        }
        sprite.wing_phase = 0.0
        for velocity in (-800.0, -400.0, 0.0, 400.0, 800.0):
            assert opaque_colours(sprite.frame(velocity)) <= expected

    def test_every_configured_colour_reaches_the_screen(self):
        sprite = BirdSprite()
        sprite.wing_phase = 0.0
        drawn = opaque_colours(sprite.frame(0.0))
        for colour in (
            settings.BIRD_COLOR,
            settings.BIRD_OUTLINE_COLOR,
            settings.BIRD_BELLY_COLOR,
            settings.BIRD_WING_COLOR,
            settings.BIRD_WING_EDGE_COLOR,
            settings.BIRD_BEAK_COLOR,
            settings.BIRD_BEAK_DARK_COLOR,
            settings.BIRD_EYE_COLOR,
            settings.BIRD_EYE_PUPIL_COLOR,
        ):
            assert colour in drawn

    def test_the_body_has_belly_wing_eye_beak_and_tail(self):
        body = "".join(BIRD_BODY_PIXELS)
        drawn = {BIRD_PALETTE[char] for char in body if char != "."}
        for colour in (
            settings.BIRD_BELLY_COLOR,
            settings.BIRD_EYE_COLOR,
            settings.BIRD_EYE_PUPIL_COLOR,
            settings.BIRD_BEAK_COLOR,
            settings.BIRD_BEAK_DARK_COLOR,
            settings.BIRD_OUTLINE_COLOR,
        ):
            assert colour in drawn
        # The pupil is a single authored pixel, and the highlight and shadow are
        # derived from the body colour, so the bird still reads as lit and shaded.
        assert body.count("p") == 1
        assert "H" in body
        assert "S" in body
        # The tail is the three leftmost columns of the silhouette.
        assert BIRD_BODY_PIXELS[5][:3] != "..."

    def test_the_wing_is_stamped_over_the_body_below_the_eye(self):
        origin_x, origin_y = settings.BIRD_WING_ORIGIN
        pose = BIRD_WING_PIXELS[0]
        # The wing must not reach up to the eye row, or the bird would go
        # blank-faced in some frames.
        assert origin_y > 7
        assert origin_y + len(pose) <= settings.BIRD_LOGICAL_SIZE
        assert origin_x + len(pose[0]) <= settings.BIRD_LOGICAL_SIZE

    def test_the_four_wing_poses_are_visibly_different(self):
        sprite = BirdSprite()
        rendered = set()
        for index in range(settings.BIRD_WING_FRAMES):
            sprite.wing_phase = (index + 0.5) / settings.BIRD_WING_FRAMES
            rendered.add(pygame.image.tostring(sprite.frame(0.0), "RGBA"))
        assert len(rendered) == settings.BIRD_WING_FRAMES

    def test_the_eye_survives_every_wing_pose(self):
        sprite = BirdSprite()
        for index in range(settings.BIRD_WING_FRAMES):
            sprite.wing_phase = (index + 0.5) / settings.BIRD_WING_FRAMES
            drawn = opaque_colours(sprite.frame(0.0))
            assert settings.BIRD_EYE_PUPIL_COLOR in drawn
            assert settings.BIRD_EYE_COLOR in drawn

    def test_the_tilt_only_rotates_the_art_it_never_redraws_it(self):
        sprite = BirdSprite()
        sprite.wing_phase = 0.0
        level = sprite.frame(0.0)
        dive = sprite.frame(800.0)
        # Different tilts, so a different orientation on a larger canvas...
        assert sprite.tilt_index(0.0) != sprite.tilt_index(800.0)
        assert (dive.get_width(), dive.get_height()) != (
            level.get_width(),
            level.get_height(),
        )
        # ...but rotation only ever drops pixels, never invents a colour.
        assert opaque_colours(dive) <= opaque_colours(level)

    def test_the_hitbox_is_still_exactly_the_bird_size(self, game):
        # Pixel art must not leak into collision: the rect is untouched.
        game.flap()
        game.update(DT)
        assert game.player.rect.size == (settings.BIRD_SIZE, settings.BIRD_SIZE)

    def test_physics_is_untouched_by_rendering(self, game):
        game.flap()
        game.update(DT)
        moved = (game.player.y, game.player.velocity_y)
        game.render()
        assert (game.player.y, game.player.velocity_y) == moved

    def test_the_sprite_canvas_is_transparent_around_the_art(self, surface):
        # The canvas is bigger than the art, so blitting cannot paint an opaque
        # rectangle over the sky.
        sprite = BirdSprite()
        frame = sprite.frame(0.0)
        assert frame.get_at((0, 0))[3] == 0
        assert frame.get_at((frame.get_width() - 1, 0))[3] == 0


class TestVisualsDoNotTouchGameplay:
    def test_visual_update_leaves_the_player_untouched(self, game):
        player = game.player
        before = (player.x, player.y, player.velocity_y, player.rect)
        for _ in range(60):
            game.visuals.update(DT)
        assert (player.x, player.y, player.velocity_y) == before[:3]
        assert player.rect == before[3]

    def test_drawing_does_not_change_the_player_rect(self, game):
        before = game.player.rect
        for state in GameState:
            game.state = state
            game.render()
            assert game.player.rect == before

    def test_drawing_does_not_change_the_player_position(self, game):
        before = (game.player.x, game.player.y, game.player.velocity_y)
        for velocity in (-520.0, 0.0, 400.0, 750.0):
            game.player.velocity_y = velocity
            game.visuals.draw_bird(game.screen, game.player)
        assert (game.player.x, game.player.y) == before[:2]

    def test_hitbox_stays_axis_aligned_while_tilted(self, game):
        game.player.velocity_y = 700.0
        game.render()
        rect = game.player.rect
        assert rect.width == rect.height == settings.BIRD_SIZE

    def test_hitbox_is_the_same_for_every_tilt(self, game):
        # Read the hitbox once before the loop, so anything the property might
        # cache is already warm and the comparison below is only about rotation.
        rects = {tuple(game.player.rect)}
        for velocity in (-520, -200, 0, 200, 520, 750):
            game.player.velocity_y = float(velocity)
            game.render()
            rects.add(tuple(game.player.rect))
        assert len(rects) == 1, "rotation must not move the hitbox"

    def test_visuals_do_not_touch_the_score(self, game):
        game.score = 5
        game.high_score = 9
        for _ in range(30):
            game.visuals.update(DT)
            game.render()
        assert game.score == 5
        assert game.high_score == 9

    def test_visuals_do_not_touch_the_pipes(self, game):
        game.pipe_manager.spawn()
        positions = [pipe.x for pipe in game.pipes]
        for _ in range(30):
            game.visuals.update(DT)
            game.render()
        assert [pipe.x for pipe in game.pipes] == positions

    def test_ground_visual_does_not_change_ground_constants(self, visuals):
        assert settings.GROUND_TOP == 680
        assert settings.GROUND_HEIGHT == 20
        visuals.ground.update(5.0)
        assert settings.GROUND_TOP == 680
        assert settings.GROUND_HEIGHT == 20


class TestTextAndPanelCaches:
    def test_text_is_rendered_once_per_string(self):
        cache = TextCache()
        font = pygame.font.Font(None, 24)
        first = cache.render(font, "Score: 0")
        assert cache.render(font, "Score: 0") is first
        assert len(cache) == 1

    def test_different_strings_are_cached_separately(self):
        cache = TextCache()
        font = pygame.font.Font(None, 24)
        assert cache.render(font, "a") is not cache.render(font, "b")
        assert len(cache) == 2

    def test_clearing_empties_the_cache(self):
        cache = TextCache()
        font = pygame.font.Font(None, 24)
        cache.render(font, "x")
        cache.clear()
        assert len(cache) == 0

    def test_panel_is_reused_for_the_same_content(self):
        cache = PanelCache()
        title = pygame.font.Font(None, 40)
        body = pygame.font.Font(None, 22)
        first = cache.render("GAME OVER", ["Score: 0"], title, body)
        assert cache.render("GAME OVER", ["Score: 0"], title, body) is first

    def test_panel_cache_is_bounded(self):
        cache = PanelCache()
        title = pygame.font.Font(None, 40)
        body = pygame.font.Font(None, 22)
        for score in range(200):
            cache.render("GAME OVER", [f"Score: {score}"], title, body)
        assert len(cache) <= cache.MAX_PANELS

    def test_panel_fits_its_longest_line(self):
        cache = PanelCache()
        title = pygame.font.Font(None, 40)
        body = pygame.font.Font(None, 22)
        panel = cache.render(
            "GAME OVER",
            ["Score: 0", "Best: 0", "Press SPACE or Click to Restart"],
            title,
            body,
        )
        longest = max(
            body.render(line, True, settings.TEXT_COLOR).get_width()
            for line in ["Score: 0", "Best: 0", "Press SPACE or Click to Restart"]
        )
        assert panel.get_width() >= longest
        assert panel.get_width() < settings.SCREEN_WIDTH

    def test_panel_draw_centers_the_card(self, surface):
        cache = PanelCache()
        title = pygame.font.Font(None, 40)
        body = pygame.font.Font(None, 22)
        surface.fill((0, 0, 0))
        cache.draw(surface, "HI", ["there"], title, body)
        center = surface.get_at(
            (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)
        )[:3]
        assert center != (0, 0, 0), "the card should cover the middle of the screen"


class TestStateRenderingStillWorks:
    def test_start_screen_renders(self, game):
        game.state = GameState.START
        game.render()
        assert bytes(settings.BIRD_COLOR) in snapshot(game.screen)

    def test_playing_screen_renders(self, game):
        game.render()
        assert bytes(settings.BIRD_COLOR) in snapshot(game.screen)

    def test_game_over_screen_renders(self, game):
        game.state = GameState.GAME_OVER
        game.score = 3
        game.high_score = 7
        game.render()
        assert bytes(settings.BIRD_COLOR) in snapshot(game.screen)

    def test_each_state_looks_different(self, game):
        seen = set()
        for state in GameState:
            game.state = state
            game.render()
            seen.add(snapshot(game.screen))
        assert len(seen) == 3

    def test_sky_and_clouds_are_drawn_behind_the_bird(self, game):
        game.render()
        assert bytes(settings.SKY_TOP_COLOR) in snapshot(game.screen)
        assert bytes(settings.CLOUD_COLOR) in snapshot(game.screen)

    def test_pipes_render(self, game):
        pipe = Pipe(x=200, gap_y=250)
        game.pipe_manager.pipes.append(pipe)
        game.render()
        assert bytes(settings.PIPE_COLOR) in snapshot(game.screen)

    def test_pipe_cap_colour_is_used(self, game):
        game.pipe_manager.pipes.append(Pipe(x=200, gap_y=250))
        game.render()
        assert bytes(settings.PIPE_CAP_COLOR) in snapshot(game.screen)

    def test_score_renders_while_playing(self, game):
        game.state = GameState.PLAYING
        game.score = 12
        before = snapshot(game.screen)
        game.score = 13
        game.render()
        assert snapshot(game.screen) != before

    def test_ground_renders_below_the_pipes(self, game):
        game.render()
        assert (
            game.screen.get_at((10, settings.GROUND_TOP + 5))[:3]
            == settings.GROUND_COLOR
        )

    def test_repeated_renders_are_identical(self, game):
        game.render()
        first = snapshot(game.screen)
        game.render()
        assert snapshot(game.screen) == first

    def test_repeated_renders_are_identical_on_the_start_screen(self, game):
        game.state = GameState.START
        game.render()
        first = snapshot(game.screen)
        game.render()
        assert snapshot(game.screen) == first


class TestPipeVisuals:
    def test_paints_the_body_colour(self, surface):
        Pipe(x=100, gap_y=300).draw(surface)
        assert bytes(settings.PIPE_COLOR) in snapshot(surface)

    def test_paints_the_cap_colour(self, surface):
        Pipe(x=100, gap_y=300).draw(surface)
        assert bytes(settings.PIPE_CAP_COLOR) in snapshot(surface)

    def test_stays_inside_the_collision_rects(self, surface):
        pipe = Pipe(x=100, gap_y=300)
        # Flood the surface with a marker colour, then draw the pipe and check
        # that no marker pixel survived inside either collision rectangle.
        surface.fill((1, 2, 3))
        pipe.draw(surface)
        for rect in pipe.rects:
            region = surface.subsurface(rect)
            assert (1, 2, 3) not in {
                region.get_at((x, y))[:3]
                for x in range(0, rect.width, 2)
                for y in range(0, rect.height, 2)
            }

    def test_drawing_does_not_change_the_geometry(self, surface):
        pipe = Pipe(x=100, gap_y=300)
        before = (pipe.x, pipe.gap_y, pipe.top_rect, pipe.bottom_rect)
        pipe.draw(surface)
        assert (pipe.x, pipe.gap_y, pipe.top_rect, pipe.bottom_rect) == before

    def test_handles_a_degenerate_gap(self, surface):
        pipe = Pipe(x=100, gap_y=0, gap=settings.PIPE_GAP_SIZE)
        pipe.draw(surface)

    def test_tiny_pipe_renders(self, surface):
        Pipe(x=100, gap_y=300, gap=4).draw(surface)


class TestSkyBanding:
    """The sky is cel shaded: flat bands with hard edges, not a smooth ramp."""

    @staticmethod
    def band_edges(sky: pygame.Surface) -> list[int]:
        """Rows where the sky colour changes."""
        return [
            y
            for y in range(1, sky.get_height())
            if sky.get_at((0, y))[:3] != sky.get_at((0, y - 1))[:3]
        ]

    def test_has_one_band_per_step(self):
        sky = build_sky()
        assert len(self.band_edges(sky)) == settings.SKY_BAND_COUNT - 1

    def test_bands_get_taller_towards_the_horizon(self):
        # A calm top of screen and stepped detail near the ground: the reverse
        # would put visible steps behind the title.
        sky = build_sky()
        edges = [0, *self.band_edges(sky), sky.get_height()]
        heights = [b - a for a, b in zip(edges, edges[1:], strict=False)]
        assert heights == sorted(heights)

    def test_every_band_is_one_flat_colour(self):
        # The joins are steps, not gradients: a whole row shares one colour.
        sky = build_sky()
        for y in range(sky.get_height()):
            row = {sky.get_at((x, y))[:3] for x in range(0, sky.get_width(), 7)}
            assert len(row) == 1

    def test_bands_step_through_the_palette(self):
        sky = build_sky()
        expected = [
            blend_color(
                settings.SKY_TOP_COLOR,
                settings.SKY_BOTTOM_COLOR,
                index / (settings.SKY_BAND_COUNT - 1),
            )
            for index in range(settings.SKY_BAND_COUNT)
        ]
        assert (
            list(dict.fromkeys(sky.get_at((0, y))[:3] for y in range(sky.get_height())))
            == expected
        )

    def test_extremes_are_exact(self):
        sky = build_sky()
        assert sky.get_at((0, 0))[:3] == settings.SKY_TOP_COLOR
        assert sky.get_at((0, sky.get_height() - 1))[:3] == settings.SKY_BOTTOM_COLOR

    def test_a_single_band_still_covers_the_screen(self):
        sky = build_sky(bands=1)
        assert sky.get_size() == (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        assert self.band_edges(sky) == []
        assert {
            sky.get_at((x, y))[:3]
            for y in range(sky.get_height())
            for x in range(0, sky.get_width(), 13)
        } == {settings.SKY_TOP_COLOR}


class TestPixelClouds:
    """Clouds are built from hard blocks on the shared pixel grid."""

    def test_block_size_is_never_fractional(self):
        for step in range(5, 30):
            assert float(cloud_block_size(step / 10)).is_integer()

    def test_every_edge_lands_on_the_pixel_grid(self):
        for scale in (0.65, 1.0, 1.45):
            block = cloud_block_size(scale)
            cloud = build_cloud(scale)
            assert cloud.get_width() % block == 0
            assert cloud.get_height() % block == 0

    def test_uses_only_the_two_cloud_colours(self):
        cloud = build_cloud(1.0)
        opaque = {
            cloud.get_at((x, y))[:3]
            for y in range(cloud.get_height())
            for x in range(cloud.get_width())
            if cloud.get_at((x, y))[3]
        }
        assert opaque == {settings.CLOUD_COLOR, settings.CLOUD_SHADE_COLOR}

    def test_colour_changes_land_on_block_boundaries(self):
        # The cloud is drawn as block-aligned rectangles, so every edge of
        # colour falls on a multiple of the block size. Anything else would mean
        # the sprite had been resampled instead of scaled up.
        block = cloud_block_size(1.0)
        cloud = build_cloud(1.0)
        width, height = cloud.get_width(), cloud.get_height()
        for y in range(height):
            for x in range(1, width):
                if cloud.get_at((x, y))[:3] != cloud.get_at((x - 1, y))[:3]:
                    assert x % block == 0, f"vertical edge at ({x}, {y})"
        for x in range(width):
            for y in range(1, height):
                if cloud.get_at((x, y))[:3] != cloud.get_at((x, y - 1))[:3]:
                    assert y % block == 0, f"horizontal edge at ({x}, {y})"

    def test_the_underside_is_shaded(self):
        cloud = build_cloud(1.0)
        bottom = cloud.get_height() - 1
        assert cloud.get_at((0, bottom))[:3] == settings.CLOUD_SHADE_COLOR

    def test_the_profile_has_no_gap(self):
        # Consecutive columns must overlap in height, or the cloud falls apart.
        assert len(CLOUD_PROFILE) == settings.CLOUD_BASE_WIDTH
        for near, far in zip(CLOUD_PROFILE, CLOUD_PROFILE[1:], strict=False):
            assert abs(near - far) <= 2


class TestDistantScenery:
    """Two silhouette bands behind the clouds, nearer ones faster and darker."""

    @staticmethod
    def field() -> SceneryField:
        return SceneryField()

    def test_has_the_two_configured_layers(self):
        assert len(self.field()) == len(DISTANT_PROFILES)

    def test_near_layers_move_faster_than_far_ones(self):
        speeds = [layer.speed for layer in self.field()]
        assert speeds == sorted(speeds)
        assert speeds[0] < speeds[-1]

    def test_near_layers_are_darker_than_far_ones(self):
        far, near = settings.DISTANT_COLORS
        assert sum(far) > sum(near), "the nearer band should read as further away"

    def test_every_layer_stands_on_the_collision_line(self):
        for layer in self.field():
            assert layer.base_y == settings.GROUND_TOP
            assert layer.top + layer.height == settings.GROUND_TOP

    def test_no_gap_can_open_between_a_layer_and_the_ground(self):
        # The bands reach the same y the ground is drawn from, so however the
        # offset lands there is always ground underneath.
        for layer in self.field():
            bottom = layer.top + layer.height
            assert bottom == settings.GROUND_TOP

    def test_update_scrolls_the_offset(self):
        layer = self.field().layers[0]
        layer.update(1.0)
        assert layer.offset > 0

    def test_offset_stays_inside_one_repeat(self):
        for layer in self.field():
            for _ in range(1000):
                layer.update(DT)
                assert 0.0 <= layer.offset < layer.tile_width

    def test_the_tile_is_a_whole_number_of_pixels_wide(self):
        for layer in self.field():
            assert layer._tile.get_width() == settings.DISTANT_TILE_WIDTH
            assert layer._tile.get_width() % settings.PIXEL_SCALE == 0

    def test_the_crest_fits_inside_its_layer(self):
        for layer, profile in zip(self.field(), DISTANT_PROFILES, strict=True):
            assert max(profile) * settings.PIXEL_SCALE <= layer.height

    def test_the_repeat_is_seamless(self):
        # The first and last columns share a height, so the join is invisible.
        for profile in DISTANT_PROFILES:
            assert profile[0] == profile[-1]

    def test_the_tile_is_transparent_above_the_crest(self):
        for layer, profile in zip(self.field(), DISTANT_PROFILES, strict=True):
            crest = layer.height - max(profile) * settings.PIXEL_SCALE
            assert crest > 0
            assert layer._tile.get_at((0, 0))[3] == 0

    def test_every_band_reaches_the_ground_at_every_column(self, surface):
        # The bands are what stand between the sky and the ground, so a single
        # uncovered column would show sky at the horizon.
        field = self.field()
        surface.fill((1, 2, 3))
        field.draw(surface)
        for layer in field:
            for x in range(surface.get_width()):
                assert surface.get_at((x, layer.base_y - 1))[:3] != (1, 2, 3)

    def test_drawing_changes_the_screen(self, surface):
        before = snapshot(surface)
        self.field().draw(surface)
        assert snapshot(surface) != before

    def test_update_never_rebuilds_the_tile(self, surface):
        # Scrolling is arithmetic; the cached silhouette is what gets blitted.
        layer = self.field().layers[0]
        tile = layer._tile
        layer.update(DT)
        layer.draw(surface)
        assert layer._tile is tile


class TestGroundArtwork:
    """The ground band is pixel art on the same grid as everything else."""

    def test_the_grass_band_is_grass_green(self):
        tile = Visuals().ground._tile
        last_grass_row = settings.GROUND_GRASS_HEIGHT - 1
        assert tile.get_at((0, last_grass_row))[:3] == settings.GROUND_COLOR

    def test_the_top_lip_is_darker_than_the_grass(self):
        tile = Visuals().ground._tile
        assert sum(tile.get_at((0, 0))[:3]) < sum(tile.get_at((0, 4))[:3])

    def test_blades_are_drawn(self):
        tile = Visuals().ground._tile
        colors = {tile.get_at((column, 4))[:3] for column in range(tile.get_width())}
        assert settings.GROUND_GRASS_BLADE_COLOR in colors

    def test_blades_sit_on_whole_pixel_columns(self):
        # A blade one pixel wide would break the shared grid.
        for column in settings.GROUND_BLADE_COLUMNS:
            assert column % settings.PIXEL_SCALE == 0

    def test_the_soil_carries_pebbles(self):
        tile = Visuals().ground._tile
        colors = {
            tile.get_at((x, y))[:3]
            for y in range(settings.GROUND_GRASS_HEIGHT, tile.get_height())
            for x in range(tile.get_width())
        }
        assert settings.GROUND_SOIL_MARK_COLOR in colors
        assert settings.GROUND_SOIL_COLOR in colors

    def test_the_repeat_stays_a_multiple_of_the_pixel_grid(self):
        assert settings.GROUND_TILE_WIDTH % settings.PIXEL_SCALE == 0


class TestDeterminism:
    """The same seed and the same ``dt`` must give the same frame, every time."""

    @staticmethod
    def render_after(seed: int, steps: int, surface: pygame.Surface) -> bytes:
        visuals = Visuals(rng=random.Random(seed))
        for _ in range(steps):
            visuals.update(DT)
        surface.fill((0, 0, 0))
        visuals.draw_sky(surface)
        visuals.draw_distant(surface)
        visuals.draw_clouds(surface)
        visuals.draw_ground(surface)
        return snapshot(surface)

    def test_the_same_seed_gives_the_same_frame(self, surface):
        first = self.render_after(11, 200, surface)
        second = self.render_after(11, 200, surface)
        assert first == second

    def test_different_seeds_give_different_frames(self, surface):
        first = self.render_after(11, 200, surface)
        other = self.render_after(12, 200, surface)
        assert first != other, "the seed has to actually reach the cloud field"

    def test_a_different_number_of_steps_gives_a_different_frame(self, surface):
        assert self.render_after(11, 200, surface) != self.render_after(
            11, 201, surface
        )

    def test_rendering_twice_never_changes_the_scene(self, surface):
        visuals = Visuals(rng=random.Random(3))
        for _ in range(60):
            visuals.update(DT)
        surface.fill((0, 0, 0))
        visuals.draw_clouds(surface)
        first = snapshot(surface)
        surface.fill((0, 0, 0))
        visuals.draw_clouds(surface)
        assert snapshot(surface) == first

    def test_an_unseeded_field_is_still_built_once(self):
        # The layout is random per scene, but it is fixed for the life of that
        # scene: nothing consults the rng again while animating.
        visuals = Visuals()
        positions = [cloud.x for cloud in visuals.clouds]
        for _ in range(120):
            visuals.update(DT)
        for cloud, before in zip(visuals.clouds, positions, strict=True):
            assert cloud.x < before


class TestAttractScreenAnimation:
    """The idle bob and the blink, which must never touch the simulation."""

    def test_the_bob_is_always_a_whole_number_of_pixels(self, visuals):
        for _ in range(600):
            visuals.update(DT, animate_bird=True, drift_clouds=False)
            assert isinstance(visuals.idle_bob, int)

    def test_the_bob_visits_every_step_in_the_table(self, visuals):
        seen = set()
        for _ in range(4000):
            visuals.update(DT, animate_bird=True, drift_clouds=False)
            seen.add(visuals.idle_bob)
        assert seen == set(settings.IDLE_BOB_STEPS)

    def test_the_bob_wraps_within_its_table(self, visuals):
        for _ in range(600):
            visuals.update(DT, animate_bird=True, drift_clouds=False)
            assert -2 <= visuals.idle_bob <= 5

    def test_zero_dt_leaves_the_bob_alone(self, visuals):
        visuals.update(0.5)
        bob = visuals.idle_bob
        visuals.update(0.0)
        assert visuals.idle_bob == bob

    def test_a_frozen_scene_stops_the_bob(self, visuals):
        visuals.update(0.5)
        bob = visuals.idle_bob
        for _ in range(120):
            visuals.update(DT, animate_bird=False, drift_clouds=False)
        assert visuals.idle_bob == bob

    def test_the_bob_never_leaves_the_centre_line(self, visuals):
        # The attract bird is drawn from a fixed centre; the bob is the only
        # thing that moves it, so the drift stays tiny.
        assert max(settings.IDLE_BOB_STEPS) - min(settings.IDLE_BOB_STEPS) <= 8

    def test_the_prompt_blinks(self, visuals):
        seen = set()
        for _ in range(4000):
            visuals.update(DT, animate_bird=True, drift_clouds=False)
            seen.add(visuals.prompt_visible)
        assert seen == {True, False}

    def test_the_prompt_is_lit_for_more_of_the_beat_than_it_is_dark(self):
        assert settings.PROMPT_VISIBLE_FRACTION > 0.5

    def test_the_wing_still_beats_on_the_attract_screen(self, visuals):
        before = visuals.bird.wing_index
        for _ in range(30):
            visuals.update(DT, animate_bird=True, drift_clouds=False)
        assert visuals.bird.wing_index != before

    def test_the_title_bird_is_the_same_sprite_only_larger(self, visuals):
        player = visuals.bird.frame(0.0)
        title = visuals.title_bird.frame(0.0)
        assert title.get_width() > player.get_width()
        assert visuals.title_bird.scale > visuals.bird.scale
        # Same authored grid, so the palette cannot have drifted between them.
        assert visuals.title_bird.logical_size == visuals.bird.logical_size

    def test_the_title_bird_flaps_too(self, visuals):
        before = visuals.title_bird.wing_index
        for _ in range(30):
            visuals.update(DT, animate_bird=True, drift_clouds=False)
        assert visuals.title_bird.wing_index != before

    def test_animating_the_scene_builds_no_new_surfaces(self, visuals):
        # Everything moving is a cached blit, so the sprite caches stay put.
        sprites = (len(visuals.bird), len(visuals.title_bird))
        tiles = visuals.clouds.clouds[0].image
        for _ in range(300):
            visuals.update(DT)
        assert (len(visuals.bird), len(visuals.title_bird)) == sprites
        assert visuals.clouds.clouds[0].image is tiles
