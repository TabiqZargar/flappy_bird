"""Tests for the hand-authored 5x7 bitmap font.

The whole look of the UI rests on this module painting hard blocks, so the tests
are mostly about geometry: that every glyph is the size it claims, that every
edge of colour lands on a block boundary, and that repeated calls come back out
of the cache rather than being rebuilt.
"""

import pygame
import pytest

from flappy_bird import settings
from flappy_bird.pixelfont import (
    ADVANCE,
    GLYPH_HEIGHT,
    GLYPH_WIDTH,
    GLYPHS,
    PixelFont,
)


@pytest.fixture(autouse=True)
def pygame_ready():
    pygame.init()
    yield


@pytest.fixture()
def surface():
    yield pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))


class TestGlyphData:
    def test_every_glyph_is_the_declared_size(self):
        for char, rows in GLYPHS.items():
            assert len(rows) == GLYPH_HEIGHT, char
            for row in rows:
                assert len(row) == GLYPH_WIDTH, char

    def test_glyphs_only_use_on_and_off_cells(self):
        for char, rows in GLYPHS.items():
            for row in rows:
                assert set(row) <= {"#", "."}, char

    def test_the_alphabet_is_complete(self):
        for code in range(ord("A"), ord("Z") + 1):
            assert chr(code) in GLYPHS

    def test_the_digits_are_complete(self):
        for digit in "0123456789":
            assert digit in GLYPHS

    def test_a_space_is_blank(self):
        assert set("".join(GLYPHS[" "])) == {"."}

    def test_no_glyph_is_blank(self):
        # A blank letter would render as a gap and look like a missing character.
        for char, rows in GLYPHS.items():
            if char == " ":
                continue
            assert any("#" in row for row in rows), char

    def test_the_advance_leaves_a_gap(self):
        assert ADVANCE == GLYPH_WIDTH + 1


class TestMeasurement:
    def test_text_width_matches_what_is_rendered(self):
        font = PixelFont()
        for text in ("A", "FLAPPY BIRD", "Score: 12"):
            label = font.render(text, 2, (255, 255, 255))
            assert label.get_width() == font.text_width(text, 2)

    def test_width_grows_with_the_scale(self):
        font = PixelFont()
        widths = [font.text_width("AB", scale) for scale in (1, 2, 3, 4)]
        assert widths == sorted(widths)
        assert widths[1] == 2 * widths[0]

    def test_an_empty_string_has_no_width(self):
        assert PixelFont.text_width("") == 0

    def test_line_height_is_the_glyph_height_times_the_scale(self):
        for scale in (1, 2, 3, 4):
            assert PixelFont.line_height(scale) == GLYPH_HEIGHT * scale

    def test_a_single_character_is_one_glyph_advancing(self):
        assert PixelFont.text_width("A", 3) == GLYPH_WIDTH * 3
        assert PixelFont.text_width("AB", 3) == (ADVANCE + GLYPH_WIDTH) * 3


class TestRendering:
    def test_every_pixel_is_a_hard_block(self):
        # The defining property: colour may only change on a multiple of the
        # scale, so each authored pixel is exactly scale-square.
        font = PixelFont()
        scale = 3
        label = font.render("MW", scale, (255, 255, 255))
        for y in range(label.get_height()):
            for x in range(1, label.get_width()):
                if label.get_at((x, y))[:3] != label.get_at((x - 1, y))[:3]:
                    assert x % scale == 0, f"vertical edge at x={x}"
        for x in range(label.get_width()):
            for y in range(1, label.get_height()):
                if label.get_at((x, y))[:3] != label.get_at((x, y - 1))[:3]:
                    assert y % scale == 0, f"horizontal edge at y={y}"

    def test_scaling_up_adds_no_new_colours(self):
        # Sampling the small label and the big one at the same authored cell has
        # to give the same colour: scaling must copy pixels, not mix them.
        font = PixelFont()
        small = font.render("FLAPPY", 1, (12, 34, 56))
        large = font.render("FLAPPY", 4, (12, 34, 56))
        for y in range(GLYPH_HEIGHT):
            for x in range(small.get_width()):
                assert small.get_at((x, y))[:3] == large.get_at((x * 4, y * 4))[:3]

    def test_the_label_is_transparent_where_there_is_no_glyph(self):
        label = PixelFont().render("A", 1, (255, 255, 255))
        assert label.get_at((0, 0))[3] == 0, "top-left of an A is blank"
        assert label.get_at((2, 0))[3] == 255, "the top of an A is lit"

    def test_the_label_is_the_colour_it_was_asked_for(self):
        label = PixelFont().render("A", 2, (10, 20, 30))
        opaque = {
            label.get_at((x, y))[:3]
            for y in range(label.get_height())
            for x in range(label.get_width())
            if label.get_at((x, y))[3]
        }
        assert opaque == {(10, 20, 30)}

    def test_lower_case_is_upper_cased(self):
        font = PixelFont()
        assert (
            font.render("ab", 2, (0, 0, 0)).get_width()
            == font.render("AB", 2, (0, 0, 0)).get_width()
        )

    def test_an_unknown_character_is_skipped_not_fatal(self):
        font = PixelFont()
        label = font.render("A&B", 2, (255, 255, 255))
        assert label.get_width() == font.text_width("A&B", 2)

    def test_empty_text_still_renders(self):
        assert PixelFont().render("", 2, (255, 255, 255)).get_width() == 1

    def test_a_scale_below_one_is_treated_as_one(self):
        font = PixelFont()
        assert font.render("A", 0, (255, 255, 255)).get_height() == GLYPH_HEIGHT


class TestShadow:
    def test_the_shadow_is_offset_by_one_block(self):
        font = PixelFont()
        shadowed = font.render_shadowed("A", 3, (255, 255, 255), (0, 0, 0))
        assert (
            shadowed.get_width() == font.render("A", 3, (255, 255, 255)).get_width() + 3
        )
        assert shadowed.get_height() == GLYPH_HEIGHT * 3 + 3

    def test_the_shadow_is_really_drawn(self):
        font = PixelFont()
        shadowed = font.render_shadowed("A", 2, (255, 255, 255), (0, 0, 0))
        colors = {
            shadowed.get_at((x, y))[:3]
            for y in range(shadowed.get_height())
            for x in range(shadowed.get_width())
            if shadowed.get_at((x, y))[3]
        }
        assert colors == {(255, 255, 255), (0, 0, 0)}

    def test_a_custom_offset_is_honoured(self):
        font = PixelFont()
        face = font.render("A", 2, (1, 1, 1))
        wide = font.render_shadowed("A", 2, (1, 1, 1), (2, 2, 2), offset=7)
        assert wide.get_width() == face.get_width() + 7


class TestCaching:
    def test_the_same_request_returns_the_same_surface(self):
        font = PixelFont()
        first = font.render("HI", 2, (0, 0, 0))
        assert font.render("HI", 2, (0, 0, 0)) is first

    def test_different_requests_are_cached_separately(self):
        font = PixelFont()
        assert font.render("HI", 2, (0, 0, 0)) is not font.render("HI", 3, (0, 0, 0))
        assert font.render("HI", 2, (0, 0, 0)) is not font.render("HI", 2, (1, 1, 1))

    def test_the_cache_is_bounded(self):
        font = PixelFont(max_entries=8)
        for index in range(200):
            font.render(str(index), 1, (0, 0, 0))
        assert len(font) <= 8

    def test_clearing_empties_the_cache(self):
        font = PixelFont()
        font.render("A", 1, (0, 0, 0))
        font.clear()
        assert len(font) == 0


class TestDrawing:
    def test_draw_reports_where_it_landed(self, surface):
        rect = PixelFont().draw(surface, "AB", 10, 20, 2, (255, 255, 255))
        assert rect.x == 10
        assert rect.y == 20
        assert rect.width == PixelFont.text_width("AB", 2)

    def test_draw_centered_centres_the_label(self, surface):
        font = PixelFont()
        width = font.text_width("ABCD", 2)
        rect = font.draw_centered(surface, "ABCD", 200, 0, 2, (255, 255, 255))
        assert rect.x == 200 - width // 2

    def test_draw_centered_accounts_for_the_shadow(self, surface):
        font = PixelFont()
        rect = font.draw_centered(
            surface, "ABCD", 200, 0, 2, (255, 255, 255), (0, 0, 0)
        )
        assert rect.width == font.text_width("ABCD", 2) + 2

    def test_drawing_lands_on_the_surface(self, surface):
        surface.fill((0, 0, 0))
        PixelFont().draw(surface, "W", 5, 5, 2, (255, 255, 255))
        assert surface.get_at((6, 8))[:3] == (255, 255, 255)
