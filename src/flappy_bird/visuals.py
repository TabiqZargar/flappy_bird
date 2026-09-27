"""Presentation layer: sky, clouds, ground, the bird sprite and UI surfaces.

Everything in this module is decorative. It reads gameplay values (a position,
a velocity) but never writes them: the collision rectangles, the physics and the
scoring state are untouched by anything drawn here.

Surfaces are expensive to build, so the static parts (the sky gradient, each
cloud, the ground tile and every bird pose) are rendered once and then blitted.
The only per-frame work is arithmetic and a handful of ``blit`` calls.
"""

from __future__ import annotations

import random

import pygame

from . import settings
from .utils import clamp, centered_rect

# --- Text -------------------------------------------------------------------


class TextCache:
    """Renders each unique string once and reuses the surface afterwards.

    Keyed by the font object as well as the text, so the title, the banner and
    the score never collide in the cache.
    """

    def __init__(self) -> None:
        self._surfaces: dict[tuple[int, str, tuple[int, int, int]], pygame.Surface] = {}

    def render(
        self,
        font: pygame.font.Font,
        text: str,
        color: tuple[int, int, int] = settings.TEXT_COLOR,
    ) -> pygame.Surface:
        key = (id(font), text, tuple(color))
        surface = self._surfaces.get(key)
        if surface is None:
            surface = font.render(text, True, color)
            self._surfaces[key] = surface
        return surface

    def clear(self) -> None:
        self._surfaces.clear()

    def __len__(self) -> int:
        return len(self._surfaces)


class PanelCache:
    """Builds centered UI cards and keeps the most recent ones around.

    The game-over card changes whenever the score does, so the cache is bounded
    and drops the oldest entry rather than growing without limit.
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
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        color: tuple[int, int, int] = settings.TEXT_COLOR,
    ) -> pygame.Surface:
        key = (title, tuple(lines), id(title_font), id(body_font), tuple(color))
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
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
        color: tuple[int, int, int],
    ) -> pygame.Surface:
        title_label = title_font.render(title, True, color)
        line_labels = [body_font.render(line, True, color) for line in lines]

        line_height = body_font.get_height()
        width = max(label.get_width() for label in [title_label, *line_labels])
        width += self.PADDING * 2
        height = (
            self.PADDING * 2
            + title_label.get_height()
            + self.LINE_GAP
            + (line_height + self.LINE_GAP) * len(line_labels)
        )

        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((255, 255, 255, 232))
        # A slim accent bar along the top edge.
        pygame.draw.rect(
            panel,
            (255, 214, 10, 255),
            pygame.Rect(0, 0, width, max(self.PADDING // 2, 2)),
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
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
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


def build_sky(
    width: int = settings.SCREEN_WIDTH,
    height: int = settings.SCREEN_HEIGHT,
    top_color: tuple[int, int, int] = settings.SKY_TOP_COLOR,
    bottom_color: tuple[int, int, int] = settings.SKY_BOTTOM_COLOR,
    bands: int = 64,
) -> pygame.Surface:
    """Build the vertical sky gradient as a single opaque surface.

    One row per band is drawn on a 1-pixel-wide surface and then stretched, so
    the whole sky costs one blit per frame regardless of the band count.
    """
    strip = pygame.Surface((1, bands))
    for index in range(bands):
        fraction = index / max(bands - 1, 1)
        strip.set_at(
            (0, index),
            tuple(
                round(top + (bottom - top) * fraction)
                for top, bottom in zip(top_color, bottom_color)
            ),
        )
    return pygame.transform.scale(strip, (width, height))


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
        scale = self.rng.uniform(
            settings.CLOUD_MIN_SCALE, settings.CLOUD_MAX_SCALE
        )
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
                cloud.recycle(
                    self.width + settings.CLOUD_SURPLUS_X
                )

    def draw(self, surface: pygame.Surface) -> None:
        for cloud in self.clouds:
            surface.blit(cloud.image, (round(cloud.x), round(cloud.y)))

    def __iter__(self):
        return iter(self.clouds)

    def __len__(self) -> int:
        return len(self.clouds)


def build_cloud(
    scale: float = 1.0,
    color: tuple[int, int, int] = settings.CLOUD_COLOR,
    shade: tuple[int, int, int] = settings.CLOUD_SHADE_COLOR,
) -> pygame.Surface:
    """Build one soft cloud from overlapping circles on a transparent surface."""
    width = max(round(settings.CLOUD_BASE_WIDTH * scale), 8)
    height = max(round(settings.CLOUD_BASE_HEIGHT * scale), 6)
    image = pygame.Surface((width, height), pygame.SRCALPHA)

    # A flat, slightly darker base keeps the cloud sitting on its own shadow.
    pygame.draw.ellipse(
        image, shade, pygame.Rect(0, height // 2, width, height // 2)
    )
    puffs = (
        (0.16, 0.62, 0.46),
        (0.42, 0.44, 0.62),
        (0.72, 0.58, 0.48),
    )
    for center_x, center_y, radius in puffs:
        radius_px = max(round(height * radius), 2)
        pygame.draw.circle(
            image,
            color,
            (
                round(width * center_x),
                round(height * center_y),
            ),
            radius_px,
        )
    return image


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
        """One repeat of the ground: a solid grass band over marked soil."""
        tile = pygame.Surface((self.tile_width, settings.GROUND_HEIGHT))
        tile.fill(settings.GROUND_SOIL_COLOR)

        # Soil texture: a short dark mark at the start of every tile, so the
        # repeat is obvious once the ground starts scrolling.
        pygame.draw.rect(
            tile,
            settings.GROUND_SOIL_MARK_COLOR,
            pygame.Rect(
                0,
                settings.GROUND_GRASS_HEIGHT,
                settings.GROUND_MARK_WIDTH,
                settings.GROUND_HEIGHT - settings.GROUND_GRASS_HEIGHT,
            ),
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


class BirdSprite:
    """Procedural bird drawn once per pose and then blitted.

    The body, wing, eye and beak are painted into a square canvas; the canvas is
    rotated for the tilt and cached under ``(tilt step, wing frame)``. Only the
    bounded set of combinations the game can reach is ever built.
    """

    def __init__(
        self,
        size: int = settings.BIRD_SIZE,
        tilt_steps: int = settings.BIRD_TILT_STEPS,
        wing_frames: int = settings.BIRD_WING_FRAMES,
    ) -> None:
        self.size = size
        self.tilt_steps = max(tilt_steps, 1)
        self.wing_frames = max(wing_frames, 1)
        self.wing_phase = 0.0
        self._frames: dict[tuple[int, int], pygame.Surface] = {}

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

    def _build(self, tilt_index: int, wing_index: int) -> pygame.Surface:
        flat = self._build_flat(wing_index)
        return pygame.transform.rotate(flat, self.cached_angles()[tilt_index])

    def _build_flat(self, wing_index: int) -> pygame.Surface:
        """Paint the unrotated bird for one wing pose."""
        size = self.size
        margin = settings.BIRD_SPRITE_MARGIN
        side = size + margin * 2
        image = pygame.Surface((side, side), pygame.SRCALPHA)
        center = side / 2
        radius = size / 2 - 2

        # Tail feathers, drawn behind the body.
        tail = [
            (center - radius + 1, center - radius * 0.45),
            (center - radius - margin + 2, center - radius * 0.85),
            (center - radius - margin + 2, center + radius * 0.10),
            (center - radius + 1, center + radius * 0.30),
        ]
        pygame.draw.polygon(image, settings.BIRD_OUTLINE_COLOR, tail)
        pygame.draw.polygon(
            image,
            settings.BIRD_BEAK_DARK_COLOR,
            [(x + 1, y) for x, y in tail],
            1,
        )

        # Body.
        body = pygame.Rect(0, 0, size, size)
        body.center = (round(center), round(center))
        pygame.draw.ellipse(
            image, settings.BIRD_OUTLINE_COLOR, body.inflate(4, 4)
        )
        pygame.draw.ellipse(image, settings.BIRD_COLOR, body)

        # Belly highlight along the bottom of the body.
        belly = pygame.Rect(0, 0, size - 8, size // 2)
        belly.center = (round(center) + 2, round(center) + radius // 2)
        pygame.draw.ellipse(image, settings.BIRD_BELLY_COLOR, belly)

        # Wing, rotated about its shoulder across the wing cycle.
        self._draw_wing(image, center, radius, wing_index)

        # Beak, pointing right.
        beak_x = center + radius - 1
        beak = [
            (beak_x, center - 5),
            (beak_x + margin + 1, center + 1),
            (beak_x, center + 6),
        ]
        pygame.draw.polygon(image, settings.BIRD_OUTLINE_COLOR, beak)
        pygame.draw.polygon(
            image,
            settings.BIRD_BEAK_COLOR,
            [(x, y) for x, y in beak],
        )
        pygame.draw.line(
            image,
            settings.BIRD_BEAK_DARK_COLOR,
            beak[0],
            (beak_x, center + 6),
            1,
        )

        # Eye: white with a pupil, plus a small brow.
        eye_center = (round(center + radius * 0.42), round(center - radius * 0.42))
        pygame.draw.circle(image, settings.BIRD_EYE_COLOR, eye_center, 6)
        pygame.draw.circle(
            image,
            settings.BIRD_OUTLINE_COLOR,
            eye_center,
            6,
            1,
        )
        pygame.draw.circle(
            image,
            settings.BIRD_EYE_PUPIL_COLOR,
            (eye_center[0] + 2, eye_center[1]),
            2,
        )
        return image

    def _draw_wing(
        self, image: pygame.Surface, center: float, radius: float, wing_index: int
    ) -> None:
        """Blit one wing pose, rotating it about the shoulder."""
        span = settings.BIRD_WING_SWING_DEGREES
        fraction = wing_index / max(self.wing_frames - 1, 1)
        angle = settings.BIRD_WING_REST_DEGREES + span * fraction

        wing_width = max(round(radius * 1.1), 4)
        wing_height = max(round(radius * 0.78), 3)
        wing = pygame.Surface((wing_width, wing_height), pygame.SRCALPHA)
        pygame.draw.ellipse(wing, settings.BIRD_OUTLINE_COLOR, wing.get_rect())
        pygame.draw.ellipse(
            wing,
            settings.BIRD_WING_COLOR,
            wing.get_rect().inflate(-2, -2),
        )
        for stripe in range(1, 3):
            y = round(wing_height * stripe / 3)
            pygame.draw.line(
                wing,
                settings.BIRD_WING_EDGE_COLOR,
                (2, y),
                (wing_width - 2, y),
                1,
            )
        wing = pygame.transform.rotate(wing, angle)

        shoulder = (round(center - radius * 0.15), round(center + radius * 0.05))
        image.blit(wing, (shoulder[0] - wing.get_width() // 2,
                          shoulder[1] - wing.get_height() // 2))

    def clear(self) -> None:
        self._frames.clear()

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
        self.ground = GroundBand(width=width)
        self.bird = BirdSprite()
        self.text = TextCache()
        self.panels = PanelCache()
        self._sky: pygame.Surface | None = None
        self.score_pulse = 0.0

    # --- Animation -----------------------------------------------------------

    def update(
        self,
        dt: float,
        animate_bird: bool = True,
        drift_clouds: bool = True,
    ) -> None:
        """Advance the decorative animation by ``dt`` seconds.

        The two flags let the game freeze the scene on the game-over screen
        while still animating the attract screen, without this module needing to
        know anything about :class:`~flappy_bird.state.GameState`.
        """
        if drift_clouds:
            self.clouds.update(dt)
            self.ground.update(dt)
        if animate_bird:
            self.bird.update(dt)
        if self.score_pulse > 0.0:
            self.score_pulse = max(0.0, self.score_pulse - dt)

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
        weight = round(fraction * settings.SCORE_PULSE_STEPS)
        if weight <= 0:
            return settings.TEXT_COLOR
        weight /= settings.SCORE_PULSE_STEPS
        return tuple(
            round(base + (bright - base) * weight)
            for base, bright in zip(settings.TEXT_COLOR, settings.SCORE_PULSE_COLOR)
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

    def draw_clouds(self, surface: pygame.Surface) -> None:
        self.clouds.draw(surface)

    def draw_ground(self, surface: pygame.Surface) -> None:
        self.ground.draw(surface)

    def draw_bird(self, surface: pygame.Surface, player) -> None:
        """Draw the player using its position and velocity only."""
        self.bird.draw(surface, player.x, player.y, player.velocity_y)


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
