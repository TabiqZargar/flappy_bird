"""Presentation layer: sky, scenery, clouds, ground, the bird sprite and UI.

Everything in this module is decorative. It reads gameplay values (a position,
a velocity) but never writes them: the collision rectangles, the physics and the
scoring state are untouched by anything drawn here.

The look is uniform pixel art. Rather than draw smooth shapes and let the
platform anti-alias them, every element is authored as a small grid of on/off
cells and blown up with ``pygame.transform.scale``, which is nearest neighbour.
The bird is the reference: a 17x17 grid, the same 5x7 font as the UI, and the
same ground, pipe and scenery blocks, all on one shared ``PIXEL_SCALE`` grid.

Surfaces are expensive to build, so the static parts (the sky bands, the scenery
tiles, each cloud, the ground tile and every bird pose) are rendered once and
then blitted. The only per-frame work is arithmetic and a handful of ``blit``
calls.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from typing import TYPE_CHECKING, Protocol

import pygame

from . import settings
from .pixelfont import PixelFont
from .utils import centered_rect, clamp

if TYPE_CHECKING:
    # For type checking only: `player` imports this module, so a runtime import
    # of Player here would be circular.
    from .player import Player

# --- Text -------------------------------------------------------------------


class Labeler(Protocol):
    """Anything that can paint a line of text and say how big it is.

    Both UI back-ends satisfy this: Pygame's bundled smooth font, and the
    hand-authored bitmap font. The caches below are written against the protocol
    rather than against one of them, so the game can mix both freely.
    """

    def render(self, text: str, color: tuple[int, int, int]) -> pygame.Surface:
        """Return a surface with ``text`` drawn in ``color``."""

    def measure(self, text: str) -> tuple[int, int]:
        """Return the ``(width, height)`` ``render`` would produce."""


class SmoothLabeler:
    """Wraps ``pygame.font.Font``, Pygame's one bundled anti-aliased font."""

    def __init__(self, font: pygame.font.Font) -> None:
        self.font = font

    def render(self, text: str, color: tuple[int, int, int]) -> pygame.Surface:
        return self.font.render(text, True, color)

    def measure(self, text: str) -> tuple[int, int]:
        # Antialiasing cannot change the advance widths, so measuring against a
        # throwaway label is the same answer as measuring against a real one.
        label = self.font.render(text, True, settings.TEXT_COLOR)
        return label.get_width(), label.get_height()


class PixelLabeler:
    """Wraps :class:`~flappy_bird.pixelfont.PixelFont` at a fixed pixel scale."""

    def __init__(self, pixelfont: PixelFont, scale: int) -> None:
        self.pixelfont = pixelfont
        self.scale = max(scale, 1)

    def render(self, text: str, color: tuple[int, int, int]) -> pygame.Surface:
        return self.pixelfont.render(text, self.scale, color)

    def measure(self, text: str) -> tuple[int, int]:
        return (
            self.pixelfont.text_width(text, self.scale),
            self.pixelfont.line_height(self.scale),
        )


#: One wrapper per font object, so cache keys stay stable across frames and the
#: caches cannot grow a second entry for the same font. The font is kept alive
#: alongside the wrapper because the key is its ``id``.
_LABELERS: dict[int, tuple[object, Labeler]] = {}


def as_labeler(renderer: object) -> Labeler:
    """Adapt ``renderer`` to the :class:`Labeler` protocol.

    Accepts an already-adapted labeler, a raw ``pygame.font.Font`` or a bare
    :class:`PixelFont` (drawn at scale 1), so callers holding either can keep
    handing it straight to the caches.
    """
    if isinstance(renderer, SmoothLabeler | PixelLabeler):
        return renderer
    cached = _LABELERS.get(id(renderer))
    if cached is not None and cached[0] is renderer:
        return cached[1]
    if isinstance(renderer, PixelFont):
        labeler: Labeler = PixelLabeler(renderer, 1)
    else:
        labeler = SmoothLabeler(renderer)  # type: ignore[arg-type]
    _LABELERS[id(renderer)] = (renderer, labeler)
    return labeler


class TextCache:
    """Renders each unique string once and reuses the surface afterwards.

    Keyed by the labeler as well as the text and colour, so the score, the title
    and the difficulty readout never collide even though they share a font.
    """

    def __init__(self) -> None:
        self._surfaces: dict[tuple[int, str, tuple[int, int, int]], pygame.Surface] = {}

    def render(
        self,
        font: object,
        text: str,
        color: tuple[int, int, int] = settings.TEXT_COLOR,
    ) -> pygame.Surface:
        labeler = as_labeler(font)
        key = (id(labeler), text, color)
        surface = self._surfaces.get(key)
        if surface is None:
            surface = labeler.render(text, color)
            self._surfaces[key] = surface
        return surface

    def clear(self) -> None:
        self._surfaces.clear()

    def __len__(self) -> int:
        return len(self._surfaces)


class PanelCache:
    """Builds blocky UI cards and keeps the most recent ones around.

    The card changes whenever the score does, so the cache is bounded and drops
    the oldest entry rather than growing without limit. Each card is a hard
    border, a light body and a drop shadow, drawn on whole pixels -- no rounded
    corners, no translucency over the world.
    """

    MAX_PANELS = 24
    PADDING = 20
    LINE_GAP = 6

    def __init__(self) -> None:
        self._panels: dict[tuple, pygame.Surface] = {}

    def render(
        self,
        title: str,
        lines: list[str],
        title_font: object,
        body_font: object,
        color: tuple[int, int, int] = settings.TEXT_COLOR,
    ) -> pygame.Surface:
        key = (
            title,
            tuple(lines),
            id(as_labeler(title_font)),
            id(as_labeler(body_font)),
            tuple(color),
        )
        panel = self._panels.get(key)
        if panel is None:
            panel = self._build(title, lines, title_font, body_font, color)
            if len(self._panels) >= self.MAX_PANELS:
                del self._panels[next(iter(self._panels))]
            self._panels[key] = panel
        return panel

    def _build(
        self,
        title: str,
        lines: list[str],
        title_font: object,
        body_font: object,
        color: tuple[int, int, int],
    ) -> pygame.Surface:
        title_labeler = as_labeler(title_font)
        body_labeler = as_labeler(body_font)
        title_label = title_labeler.render(title, color)
        line_labels = [body_labeler.render(line, color) for line in lines]

        line_height = body_labeler.measure(lines[0] if lines else "")[1]
        width = max(label.get_width() for label in [title_label, *line_labels])
        width += self.PADDING * 2
        height = (
            self.PADDING * 2
            + title_label.get_height()
            + self.LINE_GAP
            + (line_height + self.LINE_GAP) * len(line_labels)
        )

        offset = settings.PANEL_SHADOW_OFFSET
        panel = pygame.Surface((width + offset, height + offset), pygame.SRCALPHA)
        # The shadow is the whole card pushed down and right, so it reads as one
        # solid block rather than a soft glow.
        pygame.draw.rect(
            panel,
            settings.PANEL_SHADOW_COLOR,
            pygame.Rect(offset, offset, width, height),
        )
        body = pygame.Rect(0, 0, width, height)
        pygame.draw.rect(panel, settings.PANEL_FILL_COLOR, body)
        # A slim accent bar along the top edge.
        pygame.draw.rect(
            panel,
            settings.PANEL_BORDER_COLOR,
            body,
            settings.PANEL_BORDER_WIDTH,
        )
        pygame.draw.rect(
            panel,
            settings.SCORE_PULSE_COLOR,
            pygame.Rect(
                settings.PANEL_BORDER_WIDTH,
                settings.PANEL_BORDER_WIDTH,
                width - settings.PANEL_BORDER_WIDTH * 2,
                settings.PANEL_BORDER_WIDTH,
            ),
        )

        y = self.PADDING
        panel.blit(title_label, (self.PADDING, y))
        y += title_label.get_height() + self.LINE_GAP
        for label in line_labels:
            panel.blit(label, (self.PADDING, y))
            y += line_height + self.LINE_GAP
        return panel

    def draw(
        self,
        surface: pygame.Surface,
        title: str,
        lines: list[str],
        title_font: object,
        body_font: object,
        color: tuple[int, int, int] = settings.TEXT_COLOR,
    ) -> None:
        """Render (or reuse) the card and blit it centered on ``surface``."""
        panel = self.render(title, lines, title_font, body_font, color)
        surface.blit(panel, centered_rect(panel, surface.get_size()))

    def clear(self) -> None:
        self._panels.clear()

    def __len__(self) -> int:
        return len(self._panels)


# --- Sky --------------------------------------------------------------------


def blend_color(
    start: tuple[int, int, int], end: tuple[int, int, int], weight: float
) -> tuple[int, int, int]:
    """Linearly blend two RGB colours, quantised to whole channels.

    ``weight`` of 0.0 gives ``start`` and 1.0 gives ``end``. Rounding per
    channel is what lets the text cache reuse surfaces instead of building a
    new one per frame.
    """
    return (
        round(start[0] + (end[0] - start[0]) * weight),
        round(start[1] + (end[1] - start[1]) * weight),
        round(start[2] + (end[2] - start[2]) * weight),
    )


def build_sky(
    width: int = settings.SCREEN_WIDTH,
    height: int = settings.SCREEN_HEIGHT,
    top_color: tuple[int, int, int] = settings.SKY_TOP_COLOR,
    bottom_color: tuple[int, int, int] = settings.SKY_BOTTOM_COLOR,
    bands: int = settings.SKY_BAND_COUNT,
) -> pygame.Surface:
    """Build the sky as a stack of hard-edged horizontal colour bands.

    Every band is one flat colour, so the joins between them are visible steps
    rather than a smooth ramp -- the retro cel-shaded look, and the reason the
    sky reads as pixel art next to the rest of the scene.

    Band heights grow towards the horizon (``1, 2, 3, ...`` of the available
    rows). That keeps the top of the screen, where the title sits, almost
    perfectly flat, and puts the visible steps down where the eye is already
    tracking the pipes.

    The first band is exactly ``top_color`` and the last row of the screen is
    exactly ``bottom_color``, so the palette never drifts at the extremes.
    """
    sky = pygame.Surface((width, height))
    count = max(bands, 1)

    weights = list(range(1, count + 1))
    total = sum(weights)
    edges = [0]
    running = 0
    for weight in weights:
        running += weight
        edges.append(round(height * running / total))
    edges[-1] = height

    for index in range(count):
        fraction = index / max(count - 1, 1)
        top = edges[index]
        band_height = max(edges[index + 1] - top, 1)
        sky.fill(
            blend_color(top_color, bottom_color, fraction),
            pygame.Rect(0, top, width, band_height),
        )
    return sky


# --- Clouds -----------------------------------------------------------------


class Cloud:
    """One pre-rendered cloud drifting leftwards, recycled at the left edge."""

    def __init__(
        self,
        x: float,
        y: float,
        layer: int,
        speed: float,
        image: pygame.Surface,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.layer = layer
        self.speed = speed
        self.image = image

    @property
    def width(self) -> int:
        return self.image.get_width()

    @property
    def height(self) -> int:
        return self.image.get_height()

    @property
    def is_off_screen(self) -> bool:
        return self.x + self.width <= 0

    def update(self, dt: float) -> None:
        """Drift left by ``speed * dt`` seconds."""
        self.x -= self.speed * dt

    def recycle(self, x: float) -> None:
        """Re-enter from the right at ``x`` without touching the appearance."""
        self.x = float(x)


class CloudField:
    """A handful of clouds drifting at different speeds for parallax.

    The layout is generated once from an injectable ``rng``, so a test can pin
    it. Nothing here is ever read by the gameplay code.
    """

    def __init__(
        self,
        count: int = settings.CLOUD_COUNT,
        layers: int = settings.CLOUD_LAYERS,
        width: int = settings.SCREEN_WIDTH,
        rng: random.Random | None = None,
    ) -> None:
        self.width = width
        self.rng = rng or random.Random()
        self.clouds: list[Cloud] = [
            self._make_cloud(index, count, layers) for index in range(count)
        ]

    def _make_cloud(self, index: int, count: int, layers: int) -> Cloud:
        layer = index % max(layers, 1)
        scale = self.rng.uniform(settings.CLOUD_MIN_SCALE, settings.CLOUD_MAX_SCALE)
        image = build_cloud(scale)
        speed = settings.CLOUD_BASE_SPEED + layer * settings.CLOUD_LAYER_SPEED_STEP
        # Spread the starting positions so they do not arrive in a clump.
        x = self.width * (index + 1) / (count + 1)
        y = self.rng.uniform(settings.CLOUD_MIN_Y, settings.CLOUD_MAX_Y)
        return Cloud(x=x, y=y, layer=layer, speed=speed, image=image)

    def update(self, dt: float) -> None:
        """Move every cloud and wrap the ones that leave on the left."""
        for cloud in self.clouds:
            cloud.update(dt)
            if cloud.is_off_screen:
                cloud.recycle(self.width + settings.CLOUD_SURPLUS_X)

    def draw(self, surface: pygame.Surface) -> None:
        for cloud in self.clouds:
            surface.blit(cloud.image, (round(cloud.x), round(cloud.y)))

    def __iter__(self) -> Iterator[Cloud]:
        return iter(self.clouds)

    def __len__(self) -> int:
        return len(self.clouds)


#: The puffy silhouette of a cloud, one integer per authored column: how far down
#: from the top of the grid the cloud's top edge sits. Two humps with a dip
#: between them, which is what stops it reading as a rounded rectangle. Read as
#: a picture it is the outline of the cloud, upside down.
CLOUD_PROFILE: tuple[int, ...] = (
    4,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    10,
    11,
    11,
    10,
    9,
    8,
    6,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    11,
    10,
)

if len(CLOUD_PROFILE) != settings.CLOUD_BASE_WIDTH:
    raise ValueError(
        f"cloud profile has {len(CLOUD_PROFILE)} columns, "
        f"expected {settings.CLOUD_BASE_WIDTH}"
    )
if max(CLOUD_PROFILE) > settings.CLOUD_BASE_HEIGHT - settings.CLOUD_SHADE_HEIGHT:
    raise ValueError("cloud profile is taller than the grid allows")


def cloud_block_size(scale: float) -> int:
    """Whole-pixel block size for a cloud drawn at ``scale``.

    Rounding to a whole number of blocks is what keeps every cloud edge on the
    pixel grid; a fractional block would resample the authored puffs.
    """
    return max(
        settings.CLOUD_MIN_BLOCK,
        round(scale * settings.CLOUD_BLOCK_PER_SCALE),
    )


def build_cloud(
    scale: float = 1.0,
    color: tuple[int, int, int] = settings.CLOUD_COLOR,
    shade: tuple[int, int, int] = settings.CLOUD_SHADE_COLOR,
) -> pygame.Surface:
    """Build one cloud from the authored profile, on a transparent surface.

    Every column is a stack of ``block``-square cells, so the puffs are hard
    steps rather than the smooth ellipses a circle would draw. The flat rows
    along the bottom are the shaded underside.
    """
    block = cloud_block_size(scale)
    columns = settings.CLOUD_BASE_WIDTH
    rows = settings.CLOUD_BASE_HEIGHT
    width = columns * block
    height = rows * block
    image = pygame.Surface((width, height), pygame.SRCALPHA)

    body_bottom = rows - settings.CLOUD_SHADE_HEIGHT
    for column, profile in enumerate(CLOUD_PROFILE):
        top = rows - profile
        body_height = max(body_bottom - top, 0)
        if body_height:
            pygame.draw.rect(
                image,
                color,
                pygame.Rect(column * block, top * block, block, body_height * block),
            )
        pygame.draw.rect(
            image,
            shade,
            pygame.Rect(
                column * block,
                body_bottom * block,
                block,
                (rows - body_bottom) * block,
            ),
        )
    return image


# --- Distant scenery --------------------------------------------------------
#
# Two silhouette bands between the sky and the clouds. They are the depth cue:
# the far one is pale, tall and barely moving, the near one is darker, lower and
# twice as quick, so the world reads as having distance to it.

#: Silhouette of the far band: one authored column height per column of the
#: repeat. It starts and ends on the same height, so the seam is invisible.
DISTANT_FAR_PROFILE: tuple[int, ...] = (
    20,
    22,
    26,
    30,
    34,
    38,
    42,
    44,
    42,
    38,
    34,
    30,
    26,
    22,
    20,
    18,
    20,
    22,
    26,
    30,
    34,
    38,
    42,
    44,
    46,
    44,
    40,
    34,
    28,
    24,
    22,
    20,
)

#: The same trick at a lower amplitude and a finer rhythm, so the near band does
#: not look like a copy of the far one sliding behind it.
DISTANT_NEAR_PROFILE: tuple[int, ...] = (
    12,
    14,
    16,
    18,
    20,
    22,
    24,
    26,
    24,
    22,
    20,
    18,
    16,
    14,
    12,
    14,
    16,
    18,
    20,
    22,
    24,
    26,
    28,
    30,
    32,
    30,
    26,
    22,
    18,
    16,
    14,
    12,
)

DISTANT_PROFILES = (DISTANT_FAR_PROFILE, DISTANT_NEAR_PROFILE)

#: The profiles are authored on the shared pixel grid, so a repeat must be a whole
#: number of blocks wide or the blocks would not line up.
_EXPECTED_DISTANT_COLUMNS = settings.DISTANT_TILE_WIDTH // settings.PIXEL_SCALE
for _profile in DISTANT_PROFILES:
    if len(_profile) != _EXPECTED_DISTANT_COLUMNS:
        raise ValueError(
            f"distant profile has {len(_profile)} columns, "
            f"expected {_EXPECTED_DISTANT_COLUMNS}"
        )
del _profile


class SceneryLayer:
    """One cached silhouette band scrolling sideways behind the clouds.

    Only the texture offset moves. The band always stands on ``base_y``, the
    same line the ground is drawn at, so the two can never leave a gap between
    them however the offset happens to land.
    """

    #: Authored rows of rim light along the top edge of the silhouette.
    RIM_ROWS = 2

    def __init__(
        self,
        profile: tuple[int, ...],
        height: int,
        color: tuple[int, int, int],
        highlight: tuple[int, int, int],
        speed: float,
        width: int = settings.SCREEN_WIDTH,
        base_y: int = settings.DISTANT_BASE_Y,
    ) -> None:
        self.width = width
        self.height = height
        self.base_y = base_y
        self.speed = speed
        self.tile_width = settings.DISTANT_TILE_WIDTH
        self.offset = 0.0
        if max(profile) * settings.PIXEL_SCALE > height:
            raise ValueError(
                f"distant crest {max(profile)} does not fit a layer {height} tall"
            )
        self._tile = self._build(profile, color, highlight)

    def _build(
        self,
        profile: tuple[int, ...],
        color: tuple[int, int, int],
        highlight: tuple[int, int, int],
    ) -> pygame.Surface:
        """Paint one repeat of the silhouette from its column heights."""
        block = settings.PIXEL_SCALE
        tile = pygame.Surface((len(profile) * block, self.height), pygame.SRCALPHA)
        for column, value in enumerate(profile):
            top = self.height - value * block
            x = column * block
            pygame.draw.rect(
                tile,
                color,
                pygame.Rect(x, top, block, self.height - top),
            )
            # A lit rim along the crest separates the band from the sky behind it.
            pygame.draw.rect(
                tile,
                highlight,
                pygame.Rect(x, top, block, self.RIM_ROWS * block),
            )
        return tile

    @property
    def top(self) -> int:
        """Where the band starts on the y axis."""
        return self.base_y - self.height

    def update(self, dt: float) -> None:
        """Scroll left, keeping the offset inside one repeat."""
        self.offset = (self.offset + self.speed * dt) % self.tile_width

    def draw(self, surface: pygame.Surface) -> None:
        """Blit enough repeats to cover the width, starting from the offset."""
        x = -round(self.offset)
        while x < self.width:
            surface.blit(self._tile, (x, self.top))
            x += self.tile_width

    def clear_offset(self) -> None:
        self.offset = 0.0


class SceneryField:
    """The stack of distant bands, drawn far to near."""

    def __init__(self, width: int = settings.SCREEN_WIDTH) -> None:
        self.width = width
        self.layers = [
            SceneryLayer(
                profile=profile,
                height=height,
                color=color,
                highlight=highlight,
                speed=speed,
                width=width,
            )
            for profile, height, color, highlight, speed in zip(
                DISTANT_PROFILES,
                settings.DISTANT_HEIGHTS,
                settings.DISTANT_COLORS,
                settings.DISTANT_HIGHLIGHTS,
                settings.DISTANT_SPEEDS,
                strict=True,
            )
        ]

    def update(self, dt: float) -> None:
        for layer in self.layers:
            layer.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        for layer in self.layers:
            layer.draw(surface)

    def __iter__(self) -> Iterator[SceneryLayer]:
        return iter(self.layers)

    def __len__(self) -> int:
        return len(self.layers)


# --- Ground -----------------------------------------------------------------


class GroundBand:
    """The ground strip plus a repeating texture that scrolls sideways.

    Only the *texture* offset moves. The band itself is always drawn at
    ``GROUND_TOP`` with ``GROUND_HEIGHT``, so the collision line is exactly
    where the physics expects it.
    """

    TILE_WIDTH = settings.GROUND_TILE_WIDTH

    def __init__(
        self,
        width: int = settings.SCREEN_WIDTH,
        tile_width: int | None = None,
    ) -> None:
        self.width = width
        self.tile_width = tile_width or self.TILE_WIDTH
        self.offset = 0.0
        self._tile = self._build_tile()

    def _build_tile(self) -> pygame.Surface:
        """One repeat of the ground: a grass band over marked soil.

        Everything is drawn on whole-pixel rectangles. The layout is deliberate
        about two rows:

        * the row just above the soil is left as unbroken base colour, so the
          strip under the bird never flickers as the texture scrolls past;
        * the grass blades are confined to the columns and rows that leave the
          bottom of the band and the sampled ground columns alone.
        """
        tile = pygame.Surface((self.tile_width, settings.GROUND_HEIGHT))
        soil_top = settings.GROUND_GRASS_HEIGHT
        tile.fill(settings.GROUND_SOIL_COLOR)

        # Soil texture: pebbles and shadowed pockets, so the repeat is obvious
        # once the ground starts scrolling.
        for row_index, offset in enumerate(settings.GROUND_PEBBLE_ROWS):
            y = soil_top + offset
            if y >= settings.GROUND_HEIGHT:
                continue
            x = (settings.GROUND_MARK_WIDTH * row_index) % self.tile_width
            pygame.draw.rect(
                tile,
                settings.GROUND_SOIL_MARK_COLOR,
                pygame.Rect(x, y, settings.GROUND_MARK_WIDTH, 2),
            )

        # A darker lip along the very top, then unbroken grass: the band right
        # below the surface stays one flat colour.
        pygame.draw.rect(
            tile,
            settings.GROUND_GRASS_EDGE_COLOR,
            pygame.Rect(0, 0, self.tile_width, settings.GROUND_GRASS_EDGE_HEIGHT),
        )
        pygame.draw.rect(
            tile,
            settings.GROUND_COLOR,
            pygame.Rect(
                0,
                settings.GROUND_GRASS_EDGE_HEIGHT,
                self.tile_width,
                max(
                    settings.GROUND_GRASS_HEIGHT - settings.GROUND_GRASS_EDGE_HEIGHT,
                    0,
                ),
            ),
        )

        # Blades of grass poking up out of the base colour. The last grass row is
        # skipped so the flat band under the bird survives, and only the columns
        # in GROUND_BLADE_COLUMNS are used so the sampled ground columns stay on
        # the base colour too.
        for column in settings.GROUND_BLADE_COLUMNS:
            if column >= self.tile_width:
                continue
            top = settings.GROUND_GRASS_EDGE_HEIGHT
            bottom = settings.GROUND_GRASS_HEIGHT - 1
            if bottom <= top:
                continue
            pygame.draw.rect(
                tile,
                settings.GROUND_GRASS_BLADE_COLOR,
                pygame.Rect(
                    column,
                    top,
                    settings.PIXEL_SCALE,
                    bottom - top,
                ),
            )
        return tile

    @property
    def grass_top(self) -> int:
        """The collision line, unchanged by anything visual."""
        return settings.GROUND_TOP

    def update(self, dt: float, speed: float = settings.GROUND_SCROLL_SPEED) -> None:
        """Scroll the texture left, keeping the offset inside one tile."""
        self.offset = (self.offset + speed * dt) % self.tile_width

    def draw(self, surface: pygame.Surface) -> None:
        top = settings.GROUND_TOP
        surface.blit(self._tile, (-round(self.offset), top))
        # Repeat the tile across the full width to cover the seam.
        for index in range(1, self.width // self.tile_width + 2):
            surface.blit(
                self._tile,
                (-round(self.offset) + index * self.tile_width, top),
            )

    def clear_offset(self) -> None:
        self.offset = 0.0


# --- Bird -------------------------------------------------------------------


def tilt_for_velocity(velocity_y: float) -> float:
    """Tilt angle in degrees for a vertical velocity.

    Rising gives a positive (nose up) angle, falling a negative one, and the
    result is clamped so the sprite never rotates past the configured limits.
    """
    return clamp(
        -velocity_y * settings.BIRD_TILT_PER_VELOCITY,
        settings.BIRD_TILT_MIN_DEGREES,
        settings.BIRD_TILT_MAX_DEGREES,
    )


# --- The bird, as pixel art -------------------------------------------------
#
# The sprite is written out as text, one character per authored pixel, so the
# artwork is readable and editable in the source. `.` is transparent; every other
# character is looked up in `BIRD_PALETTE`. Lines are asserted to be exactly
# BIRD_LOGICAL_SIZE wide at import, so a mistyped row fails loudly instead of
# quietly shifting the sprite.

#: Highlight and shadow, derived from the body colour so the palette stays
#: closed: a shaded pixel is always a blend of two colours already in use.
BIRD_HIGHLIGHT_COLOR = blend_color(settings.BIRD_COLOR, (255, 255, 255), 0.35)
BIRD_SHADOW_COLOR = blend_color(settings.BIRD_COLOR, settings.BIRD_OUTLINE_COLOR, 0.55)

BIRD_PALETTE: dict[str, tuple[int, int, int]] = {
    "O": settings.BIRD_OUTLINE_COLOR,
    "H": BIRD_HIGHLIGHT_COLOR,
    "B": settings.BIRD_COLOR,
    "E": settings.BIRD_BELLY_COLOR,
    "S": BIRD_SHADOW_COLOR,
    "k": settings.BIRD_BEAK_COLOR,
    "d": settings.BIRD_BEAK_DARK_COLOR,
    "w": settings.BIRD_EYE_COLOR,
    "p": settings.BIRD_EYE_PUPIL_COLOR,
    "W": settings.BIRD_WING_COLOR,
    "X": settings.BIRD_WING_EDGE_COLOR,
}

#: The bird, 17 x 17, facing right: tail, body, belly, eye, beak.
BIRD_BODY_PIXELS: tuple[str, ...] = (
    ".................",
    "......OOOOO......",
    "....OOHHHHHOO....",
    "...OHHHHHBBBBB...",
    "...OHHHBBBBBBS...",
    "OOOOHHBBBBBBBS...",
    "OOOHBwpBBBBBBBSkk",
    "OOOBBwwBBBBBBBSkk",
    "SSSBBBBBBBBBBBSdd",
    "SSSBBBBBBBBBBBSdd",
    "SSSBBBBBBBBBBBSdd",
    "SS.OBEEEEEEESS...",
    "...OBBEEEEEBBS...",
    "...OBBEEEEBBSS...",
    "....OOSSSSOO.....",
    "......OOOO.......",
    ".................",
)
#: Four wing poses, 6 x 3, the root pinned at the left and the tip beating.
BIRD_WING_PIXELS: tuple[tuple[str, ...], ...] = (
    ("OWWWWW", "OWWXWW", "OXXWXW"),
    ("OWWXWW", "OWWWWW", "OXXXWW"),
    ("OXXWXW", "OWWXWW", "OWWWWW"),
    ("OXXWXX", "OXXXWW", "OWWXWW"),
)


def _check_pixel_rows(rows: tuple[str, ...], width: int, name: str) -> None:
    """Fail at import if a drawn row is not exactly ``width`` pixels wide."""
    for index, line in enumerate(rows):
        if len(line) != width:
            raise ValueError(
                f"{name} row {index} is {len(line)} pixels wide, expected {width}"
            )
        unknown = set(line) - set(BIRD_PALETTE) - {"."}
        if unknown:
            raise ValueError(f"{name} row {index} has unknown pixels {sorted(unknown)}")


_check_pixel_rows(BIRD_BODY_PIXELS, settings.BIRD_LOGICAL_SIZE, "bird body")
for _pose_index, _pose in enumerate(BIRD_WING_PIXELS):
    _check_pixel_rows(_pose, len(BIRD_WING_PIXELS[0][0]), f"bird wing {_pose_index}")
del _pose_index, _pose


class BirdSprite:
    """A hand-drawn pixel bird, built once per pose and then blitted.

    The artwork is authored on a 17-pixel logical grid, the wing is stamped on
    top for the current wing frame, and the whole thing is rotated for the tilt
    and scaled up by an integer factor with ``pygame.transform.scale``. Scaling
    is nearest neighbour, so the result is the same artwork with every pixel
    turned into a hard square block -- no smoothing and no anti-aliasing.

    Poses are cached under ``(tilt step, wing frame)``, so only the bounded set
    of combinations the game can reach is ever built, and nothing is rebuilt
    per frame.
    """

    def __init__(
        self,
        size: int = settings.BIRD_SIZE,
        tilt_steps: int = settings.BIRD_TILT_STEPS,
        wing_frames: int = settings.BIRD_WING_FRAMES,
        scale: int = settings.BIRD_PIXEL_SCALE,
    ) -> None:
        self.size = size
        self.tilt_steps = max(tilt_steps, 1)
        self.wing_frames = max(wing_frames, 1)
        self.scale = max(scale, 1)
        self.wing_phase = 0.0
        self._frames: dict[tuple[int, int], pygame.Surface] = {}
        self._logical: dict[int, pygame.Surface] = {}

    # --- Animation -----------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the wing cycle by ``dt`` seconds, wrapping at one full beat."""
        beat = self.wing_phase + dt * settings.BIRD_WING_FRAMES_PER_SECOND
        self.wing_phase = beat % 1.0

    @property
    def wing_index(self) -> int:
        """Which of the wing poses the current phase falls in."""
        index = int(self.wing_phase * self.wing_frames)
        return min(index, self.wing_frames - 1)

    def tilt_degrees(self, velocity_y: float) -> float:
        """The clamped tilt used for a velocity, before quantization."""
        return tilt_for_velocity(velocity_y)

    def tilt_index(self, velocity_y: float) -> int:
        """Bucket a tilt into one of the pre-rendered rotations."""
        span = settings.BIRD_TILT_MAX_DEGREES - settings.BIRD_TILT_MIN_DEGREES
        raw = self.tilt_degrees(velocity_y) - settings.BIRD_TILT_MIN_DEGREES
        index = int(raw / span * self.tilt_steps)
        return min(max(index, 0), self.tilt_steps - 1)

    def cached_angles(self) -> list[float]:
        """The exact angle of every tilt bucket, in degrees."""
        span = settings.BIRD_TILT_MAX_DEGREES - settings.BIRD_TILT_MIN_DEGREES
        step = span / self.tilt_steps
        return [
            settings.BIRD_TILT_MIN_DEGREES + (index + 0.5) * step
            for index in range(self.tilt_steps)
        ]

    # --- Drawing -------------------------------------------------------------

    def frame(self, velocity_y: float) -> pygame.Surface:
        """The cached sprite for a velocity and the current wing phase."""
        key = (self.tilt_index(velocity_y), self.wing_index)
        sprite = self._frames.get(key)
        if sprite is None:
            sprite = self._build(key[0], key[1])
            self._frames[key] = sprite
        return sprite

    def draw(
        self,
        surface: pygame.Surface,
        x: float,
        y: float,
        velocity_y: float = 0.0,
    ) -> None:
        """Blit the bird centered on ``(x, y)``; the hitbox is never touched."""
        sprite = self.frame(velocity_y)
        surface.blit(
            sprite,
            (
                round(x) - sprite.get_width() // 2,
                round(y) - sprite.get_height() // 2,
            ),
        )

    @property
    def logical_size(self) -> int:
        """Side length of the pre-scale canvas, in authored pixels."""
        return settings.BIRD_LOGICAL_SIZE + settings.BIRD_PIXEL_MARGIN * 2

    def logical_frame(self, wing_index: int) -> pygame.Surface:
        """The unrotated, unscaled pixel grid for one wing pose.

        Exposed so the scale factor and the palette can be checked without
        guessing at the final surface. Cached, like the poses themselves.
        """
        frame = self._logical.get(wing_index)
        if frame is None:
            frame = self._build_logical(wing_index)
            self._logical[wing_index] = frame
        return frame

    def _build(self, tilt_index: int, wing_index: int) -> pygame.Surface:
        """Rotate the pixel grid for the tilt, then scale it up by whole pixels."""
        rotated = pygame.transform.rotate(
            self.logical_frame(wing_index), self.cached_angles()[tilt_index]
        )
        # `scale` is nearest neighbour; `smoothscale` would blend the palette
        # into new colours and undo the pixel art.
        return pygame.transform.scale(
            rotated,
            (
                rotated.get_width() * self.scale,
                rotated.get_height() * self.scale,
            ),
        )

    def _build_logical(self, wing_index: int) -> pygame.Surface:
        """Paint the authored pixels, plus the wing, onto the logical canvas."""
        side = self.logical_size
        margin = settings.BIRD_PIXEL_MARGIN
        image = pygame.Surface((side, side), pygame.SRCALPHA)

        rows = BIRD_BODY_PIXELS
        for y, line in enumerate(rows):
            for x, char in enumerate(line):
                color = BIRD_PALETTE.get(char)
                if color is not None:
                    image.set_at((x + margin, y + margin), color)

        # The wing is stamped over the body, so it animates without disturbing
        # the silhouette, the eye or the beak.
        wing = BIRD_WING_PIXELS[wing_index % len(BIRD_WING_PIXELS)]
        origin_x, origin_y = settings.BIRD_WING_ORIGIN
        for y, line in enumerate(wing):
            for x, char in enumerate(line):
                color = BIRD_PALETTE.get(char)
                if color is not None:
                    image.set_at((x + origin_x + margin, y + origin_y + margin), color)
        return image

    def clear(self) -> None:
        self._frames.clear()
        self._logical.clear()

    def __len__(self) -> int:
        return len(self._frames)


# --- Facade -----------------------------------------------------------------


class Visuals:
    """Everything decorative, updated with an explicit ``dt``.

    ``update`` never touches the player, the pipes or the score, so the scene can
    animate freely without any risk to the simulation.
    """

    def __init__(
        self,
        width: int = settings.SCREEN_WIDTH,
        height: int = settings.SCREEN_HEIGHT,
        rng: random.Random | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.clouds = CloudField(width=width, rng=rng)
        self.distant = SceneryField(width=width)
        self.ground = GroundBand(width=width)
        self.bird = BirdSprite()
        # The same sprite again, one size up: the attract screen gets a big bird
        # for free instead of a second, separately authored piece of artwork.
        self.title_bird = BirdSprite(scale=settings.TITLE_BIRD_SCALE)
        self.pixelfont = PixelFont()
        self.text = TextCache()
        self.panels = PanelCache()
        self._sky: pygame.Surface | None = None
        self._labelers: dict[int, PixelLabeler] = {}
        self.score_pulse = 0.0
        self.idle_phase = 0.0

    # --- Animation -----------------------------------------------------------

    def update(
        self,
        dt: float,
        animate_bird: bool = True,
        drift_clouds: bool = True,
    ) -> None:
        """Advance the decorative animation by ``dt`` seconds.

        The two flags let the game freeze the scene on the game-over screen while
        still animating the attract screen, without this module needing to know
        anything about :class:`~flappy_bird.state.GameState`.

        The attract-screen bob rides on ``animate_bird`` alongside the wing beat,
        which is deliberate: on ``START`` there is no physics to read a tilt from,
        so the wing animation is the only thing the player sprite could show.
        """
        if drift_clouds:
            self.clouds.update(dt)
            self.distant.update(dt)
            self.ground.update(dt)
        if animate_bird:
            self.bird.update(dt)
            self.title_bird.update(dt)
            self.idle_phase = (
                self.idle_phase + dt / settings.IDLE_BOB_STEP_SECONDS
            ) % 1.0
        if self.score_pulse > 0.0:
            self.score_pulse = max(0.0, self.score_pulse - dt)

    @property
    def idle_bob(self) -> int:
        """Vertical offset of the attract-screen bird, in whole pixels.

        Read from a fixed table rather than a sine, so the offset is always an
        integer and the bird never lands between two pixel rows.
        """
        steps = settings.IDLE_BOB_STEPS
        index = int(self.idle_phase * len(steps))
        return steps[min(index, len(steps) - 1)]

    @property
    def prompt_visible(self) -> bool:
        """Whether the start prompt is lit on this beat.

        Driven off the same phase as the bob, so it stays on the pixel grid and
        costs nothing to keep in step with it.
        """
        return (self.idle_phase * 4) % 1.0 < settings.PROMPT_VISIBLE_FRACTION

    # --- Game feel -----------------------------------------------------------

    def pulse_score(self) -> None:
        """Flash the running score; purely decorative feedback for a point."""
        self.score_pulse = settings.SCORE_PULSE_SECONDS

    def score_color(self) -> tuple[int, int, int]:
        """Text colour for the running score, brighter while the pulse lasts.

        The blend is quantised to ``SCORE_PULSE_STEPS`` levels so the text cache
        gains a handful of variants per score instead of one per frame.
        """
        fraction = self.score_pulse / settings.SCORE_PULSE_SECONDS
        if fraction <= 0.0:
            return settings.TEXT_COLOR
        steps = round(fraction * settings.SCORE_PULSE_STEPS)
        if steps <= 0:
            return settings.TEXT_COLOR
        return blend_color(
            settings.TEXT_COLOR,
            settings.SCORE_PULSE_COLOR,
            steps / settings.SCORE_PULSE_STEPS,
        )

    # --- Drawing -------------------------------------------------------------

    @property
    def sky(self) -> pygame.Surface:
        """The cached sky gradient, built on first use."""
        if self._sky is None:
            self._sky = build_sky(self.width, self.height)
        return self._sky

    def draw_sky(self, surface: pygame.Surface) -> None:
        surface.blit(self.sky, (0, 0))

    def draw_distant(self, surface: pygame.Surface) -> None:
        """Draw the silhouette bands, between the sky and the clouds."""
        self.distant.draw(surface)

    def draw_clouds(self, surface: pygame.Surface) -> None:
        self.clouds.draw(surface)

    def draw_ground(self, surface: pygame.Surface) -> None:
        self.ground.draw(surface)

    def draw_bird(self, surface: pygame.Surface, player: Player) -> None:
        """Draw the player using its position and velocity only."""
        self.bird.draw(surface, player.x, player.y, player.velocity_y)

    def draw_title_bird(self, surface: pygame.Surface) -> None:
        """Draw the oversized attract-screen bird at its idle bob.

        The offset is added here and nowhere else, so ``player.y`` stays exactly
        where the physics left it: the attract screen animates without the bird
        ever being part of the simulation.
        """
        self.title_bird.draw(
            surface,
            settings.TITLE_BIRD_X,
            settings.TITLE_BIRD_Y + self.idle_bob,
        )

    # --- Pixel text ----------------------------------------------------------

    def labeler(self, scale: int) -> PixelLabeler:
        """The cached pixel labeler for a scale, so callers can share one."""
        labeler = self._labelers.get(scale)
        if labeler is None:
            labeler = PixelLabeler(self.pixelfont, scale)
            self._labelers[scale] = labeler
        return labeler

    def draw_centered_text(
        self,
        surface: pygame.Surface,
        text: str,
        y: int,
        scale: int,
        color: tuple[int, int, int] = settings.TEXT_COLOR,
        shadow: tuple[int, int, int] | None = settings.TEXT_SHADOW_COLOR,
    ) -> pygame.Rect:
        """Draw one centred line of pixel text, shadowed by default."""
        return self.pixelfont.draw_centered(
            surface,
            text,
            self.width // 2,
            y,
            scale,
            color,
            shadow,
        )


#: Shared sprite for callers that only have a player and no scene, such as
#: ``Player.draw``.
_default_sprite: BirdSprite | None = None


def default_bird_sprite() -> BirdSprite:
    """A lazily built, wing-still bird for standalone drawing."""
    global _default_sprite
    if _default_sprite is None:
        _default_sprite = BirdSprite()
        _default_sprite.wing_phase = 0.0
    return _default_sprite


def draw_bird(
    surface: pygame.Surface,
    x: float,
    y: float,
    velocity_y: float = 0.0,
) -> None:
    """Draw the bird with the shared, unanimated sprite."""
    default_bird_sprite().draw(surface, x, y, velocity_y)
