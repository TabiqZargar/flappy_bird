"""A hand-authored 5x7 bitmap font, rendered as crisp pixel blocks.

Pygame ships only one font, and it is a smooth TrueType face: at the sizes this
game uses it renders anti-aliased curves that clash with the pixel art. Rather
than ship a font file, the glyphs are written out here as text -- one character
per pixel, exactly like the bird sprite -- and painted into a surface at a whole
number of times their authored size.

``pygame.transform.scale`` is nearest neighbour, so every authored pixel becomes
a hard square block, which is what keeps the UI in the same visual language as
the world.

The font is pure data plus rendering: it knows nothing about the game, and it
never touches gameplay state.
"""

from __future__ import annotations

import pygame

#: Authored glyph size. Advance is one extra pixel of spacing per character.
GLYPH_WIDTH = 5
GLYPH_HEIGHT = 7
ADVANCE = GLYPH_WIDTH + 1

#: Each glyph is GLYPH_HEIGHT rows of GLYPH_WIDTH characters, `#` for on and `.`
#: for off. Reading the rows as a picture is the whole point of writing them this
#: way, so they are checked for the right shape at import rather than trusted.
GLYPHS: dict[str, tuple[str, ...]] = {
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#...#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    ":": (".....", "..#..", "..#..", ".....", "..#..", "..#..", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ",": (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    "'": ("..#..", "..#..", ".....", ".....", ".....", ".....", "....."),
    "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
}


def _check_glyphs() -> None:
    """Fail at import on a mistyped row rather than a shifted glyph."""
    for char, rows in GLYPHS.items():
        if len(rows) != GLYPH_HEIGHT:
            raise ValueError(
                f"glyph {char!r} has {len(rows)} rows, expected {GLYPH_HEIGHT}"
            )
        for index, row in enumerate(rows):
            if len(row) != GLYPH_WIDTH:
                raise ValueError(
                    f"glyph {char!r} row {index} is {len(row)} pixels wide, "
                    f"expected {GLYPH_WIDTH}"
                )


_check_glyphs()


class PixelFont:
    """Renders strings in the authored 5x7 font at whole-pixel scales.

    Surfaces are cached per ``(text, scale, color)``, so the handful of strings the
    game shows are painted once and then blitted. ``scale`` must be at least 1:
    the result is ``GLYPH_HEIGHT * scale`` pixels tall and every pixel of it is a
    hard ``scale``-square block.
    """

    def __init__(self, max_entries: int = 256) -> None:
        self.max_entries = max_entries
        # Keyed by (text, scale, colours). A plain label stores one colour; a
        # shadowed one stores its colour, the shadow colour and the drop, which
        # is why the colour slot is a variable-length tuple.
        self._surfaces: dict[tuple[str, int, tuple[int, ...]], pygame.Surface] = {}

    # --- Measurement ---------------------------------------------------------

    @staticmethod
    def text_width(text: str, scale: int = 1) -> int:
        """Width of ``text`` in pixels, spacing included."""
        if not text:
            return 0
        return len(text) * ADVANCE * scale - scale

    @staticmethod
    def line_height(scale: int = 1) -> int:
        """Height of one line in pixels."""
        return GLYPH_HEIGHT * scale

    # --- Rendering -----------------------------------------------------------

    def render(
        self,
        text: str,
        scale: int = 1,
        color: tuple[int, int, int] = (255, 255, 255),
    ) -> pygame.Surface:
        """Return the cached surface for ``text``, building it on first use."""
        scale = max(scale, 1)
        key = (text, scale, color)
        surface = self._surfaces.get(key)
        if surface is None:
            surface = self._build(text, scale, color)
            if len(self._surfaces) >= self.max_entries:
                del self._surfaces[next(iter(self._surfaces))]
            self._surfaces[key] = surface
        return surface

    def render_shadowed(
        self,
        text: str,
        scale: int = 1,
        color: tuple[int, int, int] = (255, 255, 255),
        shadow: tuple[int, int, int] = (0, 0, 0),
        offset: int | None = None,
    ) -> pygame.Surface:
        """Render ``text`` with a hard offset shadow, as one cached surface.

        Building the shadow into the same surface keeps the pair cacheable and
        stops the two halves from drifting apart between frames.
        """
        scale = max(scale, 1)
        drop = scale if offset is None else offset
        key = ("shadow:" + text, scale, color + shadow + (drop,))
        surface = self._surfaces.get(key)
        if surface is None:
            face = self.render(text, scale, color)
            surface = pygame.Surface(
                (face.get_width() + drop, face.get_height() + drop), pygame.SRCALPHA
            )
            dark = self.render(text, scale, shadow)
            surface.blit(dark, (drop, drop))
            surface.blit(face, (0, 0))
            if len(self._surfaces) >= self.max_entries:
                del self._surfaces[next(iter(self._surfaces))]
            self._surfaces[key] = surface
        return surface

    def _build(
        self, text: str, scale: int, color: tuple[int, int, int]
    ) -> pygame.Surface:
        """Paint the glyphs of ``text`` onto a transparent surface.

        Transparent rather than opaque, because these labels get blitted over
        the sky, over a card and over each other, and a label that assumed a
        background colour would drag that colour along with it.
        """
        width = self.text_width(text, scale)
        height = self.line_height(scale)
        surface = pygame.Surface((max(width, 1), height), pygame.SRCALPHA)

        for index, char in enumerate(text.upper()):
            rows = GLYPHS.get(char)
            if rows is None:
                continue  # unknown characters are simply skipped, never crash
            origin_x = index * ADVANCE * scale
            for y, row in enumerate(rows):
                for x, cell in enumerate(row):
                    if cell == "#":
                        surface.fill(
                            color,
                            pygame.Rect(
                                origin_x + x * scale,
                                y * scale,
                                scale,
                                scale,
                            ),
                        )
        return surface

    def draw(
        self,
        surface: pygame.Surface,
        text: str,
        x: int,
        y: int,
        scale: int = 1,
        color: tuple[int, int, int] = (255, 255, 255),
        shadow: tuple[int, int, int] | None = None,
    ) -> pygame.Rect:
        """Blit ``text`` at an integer position and report where it landed."""
        if shadow is None:
            label = self.render(text, scale, color)
            surface.blit(label, (x, y))
            return pygame.Rect(x, y, label.get_width(), label.get_height())
        label = self.render_shadowed(text, scale, color, shadow)
        surface.blit(label, (x, y))
        return pygame.Rect(x, y, label.get_width(), label.get_height())

    def draw_centered(
        self,
        surface: pygame.Surface,
        text: str,
        center_x: int,
        y: int,
        scale: int = 1,
        color: tuple[int, int, int] = (255, 255, 255),
        shadow: tuple[int, int, int] | None = None,
    ) -> pygame.Rect:
        """Blit ``text`` horizontally centred on ``center_x``."""
        width = self.text_width(text, scale)
        if shadow is not None:
            width += scale
        return self.draw(surface, text, center_x - width // 2, y, scale, color, shadow)

    def clear(self) -> None:
        self._surfaces.clear()

    def __len__(self) -> int:
        return len(self._surfaces)
