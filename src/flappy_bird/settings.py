"""Central configuration for the game.

Every tunable value lives here so gameplay code stays free of magic numbers.
"""

# --- Window -----------------------------------------------------------------

SCREEN_WIDTH = 400
SCREEN_HEIGHT = 700
FPS = 60
CAPTION = "Flappy Bird"

# --- Player -----------------------------------------------------------------

BIRD_START_X = 90
BIRD_START_Y = 300
BIRD_SIZE = 34
BIRD_COLOR = (255, 214, 10)
BIRD_OUTLINE_COLOR = (60, 42, 0)
BIRD_BELLY_COLOR = (255, 243, 176)
BIRD_WING_COLOR = (240, 170, 6)
BIRD_WING_EDGE_COLOR = (176, 118, 0)
BIRD_BEAK_COLOR = (255, 140, 0)
BIRD_BEAK_DARK_COLOR = (214, 96, 0)
BIRD_EYE_COLOR = (255, 255, 255)
BIRD_EYE_PUPIL_COLOR = (38, 30, 18)

# --- Physics ----------------------------------------------------------------

GRAVITY = 1250.0
JUMP_VELOCITY = -370.0
MAX_FALL_SPEED = 750.0
MAX_FRAME_TIME = 1.0 / 15.0
GROUND_HEIGHT = 20

# --- Playable area ----------------------------------------------------------

CEILING_Y = 0
GROUND_TOP = SCREEN_HEIGHT - GROUND_HEIGHT

# --- Pipes ------------------------------------------------------------------

PIPE_WIDTH = 60
PIPE_GAP_SIZE = 160
PIPE_MIN_GAP_CENTER = 160
PIPE_MAX_GAP_CENTER = 540
PIPE_SPEED = 120.0
PIPE_SPAWN_INTERVAL = 2.0
PIPE_COLOR = (34, 177, 76)
PIPE_EDGE_COLOR = (20, 105, 45)
PIPE_CAP_COLOR = (28, 152, 64)
PIPE_CAP_HEIGHT = 26
PIPE_HIGHLIGHT_COLOR = (108, 214, 138)
PIPE_SHADOW_COLOR = (16, 88, 40)
PIPE_HIGHLIGHT_WIDTH = 6
PIPE_SHADOW_WIDTH = 4

# --- Difficulty -------------------------------------------------------------
#
# The ladder is derived from the pipe constants above, which stay exactly as they
# were: level 0 *is* the original game. Each step tightens the pipes a little,
# and every step is clamped, so the last level is the end of the road.

#: Points needed per difficulty level.
DIFFICULTY_SCORE_STEP = 5
#: Highest level; reached at 25 points, after which the game stops getting harder.
DIFFICULTY_MAX_LEVEL = 5

#: Extra pixels per second added to PIPE_SPEED on each level (+40 at level 5).
DIFFICULTY_SPEED_INCREMENT = 8.0
#: Hard cap on pipe speed, however long the run goes on.
DIFFICULTY_MAX_SPEED = 160.0

#: Pixels removed from PIPE_GAP_SIZE on each level (-40 at level 5).
DIFFICULTY_GAP_DECREMENT = 8
#: Hard floor on the gap. Still ~3.5x the bird, so the last level is fair.
DIFFICULTY_MIN_GAP = 120

#: Seconds removed from PIPE_SPAWN_INTERVAL on each level (-0.4s at level 5).
DIFFICULTY_SPAWN_DECREMENT = 0.08
#: Hard floor on the spawn interval, so pipes can never arrive faster than this.
#: Reached exactly at level 5, like the speed ceiling and the gap floor.
DIFFICULTY_MIN_SPAWN_INTERVAL = 1.6

# --- Pixel grid --------------------------------------------------------------
#
# Every element on screen is built out of whole-pixel blocks on one shared grid:
# the bird, the clouds, the distant scenery, the ground, the pipes and the 5x7 UI
# font. They all snapping to the same block size is what makes the scene read as
# one piece of pixel art rather than a set of unrelated shapes.

#: Size of one authored pixel in real pixels, for the whole world.
PIXEL_SCALE = 2

# --- Presentation -----------------------------------------------------------

BACKGROUND_COLOR = (233, 236, 239)
GROUND_COLOR = (126, 196, 74)
TEXT_COLOR = (54, 54, 54)
SCORE_FONT_SIZE = 28
SCORE_TEXT_Y = 88
#: A quiet level readout tucked under the score; only visible while playing.
DIFFICULTY_FONT_SIZE = 15
DIFFICULTY_TEXT_Y = 126
DIFFICULTY_TEXT_COLOR = (58, 92, 122)
BANNER_FONT_SIZE = 22
TITLE_FONT_SIZE = 46

# --- Pixel UI ----------------------------------------------------------------
#
# The UI is drawn with the hand-authored 5x7 bitmap font in ``pixelfont`` rather
# than Pygame's single bundled TrueType face, which renders smooth anti-aliased
# curves that look out of place next to the world. Each scale below multiplies
# the authored glyph size, so a glyph is always a whole number of pixels tall and
# every one of its pixels a hard ``scale``-square block.

#: Big score, centred at the top of the screen while playing.
SCORE_TEXT_SCALE = 4
#: The small level readout under the score.
DIFFICULTY_TEXT_SCALE = 2
#: "FLAPPY BIRD" on the attract screen.
TITLE_TEXT_SCALE = 4
#: Panel headings ("GAME OVER").
PANEL_TITLE_SCALE = 3
#: Panel body lines.
PANEL_TEXT_SCALE = 2

#: The title sits high on the screen, against the darkest band of the sky, so it
#: is light with a darker offset shadow -- the classic arcade outline.
TEXT_PANEL_COLOR = (72, 104, 136)
TEXT_TITLE_COLOR = (255, 255, 255)
TEXT_SHADOW_COLOR = (36, 72, 112)
#: Body text sits on a light card, so it is dark with a pale shadow instead.
PANEL_TEXT_SHADOW_COLOR = (255, 255, 255)
#: The quiet controls hint under the prompt, kept low-contrast on purpose.
TEXT_HINT_COLOR = (70, 96, 124)

#: Outline of the game-over / start card, and its body fill.
PANEL_BORDER_COLOR = (48, 84, 124)
PANEL_FILL_COLOR = (247, 251, 253)
PANEL_SHADOW_COLOR = (28, 56, 88)
#: Border thickness, in pixels.
PANEL_BORDER_WIDTH = 4
#: Distance the card is offset from its own shadow.
PANEL_SHADOW_OFFSET = 6

# --- Sky and clouds ---------------------------------------------------------

SKY_TOP_COLOR = (94, 190, 242)
SKY_BOTTOM_COLOR = (206, 238, 252)
CLOUD_COLOR = (255, 255, 255)
CLOUD_SHADE_COLOR = (223, 238, 250)
CLOUD_COUNT = 6
CLOUD_LAYERS = 2
CLOUD_BASE_SPEED = 7.0
CLOUD_LAYER_SPEED_STEP = 5.0
CLOUD_MIN_SCALE = 0.65
CLOUD_MAX_SCALE = 1.45
CLOUD_MIN_Y = 40
CLOUD_MAX_Y = 430
CLOUD_BASE_WIDTH = 24
CLOUD_BASE_HEIGHT = 14
CLOUD_SURPLUS_X = 140  # how far past the right edge a recycled cloud returns
#: Rows of shade along the flat underside of a cloud, in authored pixels.
CLOUD_SHADE_HEIGHT = 3
#: One cloud is an authored 24x12 grid blown up by a whole-number block size, so
#: its puffs are the same hard squares as the rest of the world. The block size
#: comes from the scale, rounded to a whole number of blocks: clouds never get a
#: half-pixel edge.
CLOUD_BLOCK_PER_SCALE = 3.0
CLOUD_MIN_BLOCK = 2

#: Horizontal steps in the sky. Deliberately few: each band ends on a hard edge,
#: so the sky reads as retro cel shading instead of a smooth ramp. The band
#: heights grow towards the horizon, which keeps the top of the screen calm and
#: puts the visible steps where the eye is.
SKY_BAND_COUNT = 12

# --- Distant scenery --------------------------------------------------------
#
# Two silhouette layers between the sky and the clouds, both scrolling slowly
# enough to feel far away. They give the world depth without competing with the
# clouds or the pipes.

#: Palette of the two layers, far (paler, taller) then near (darker, lower).
DISTANT_COLORS = ((150, 200, 176), (108, 172, 150))
DISTANT_HIGHLIGHTS = ((178, 218, 194), (134, 194, 168))
#: Height of each band. Only as tall as its crest needs, so the layer does not
#: carry a slab of empty transparency above the hills.
DISTANT_HEIGHTS = (96, 66)
DISTANT_SPEEDS = (8.0, 16.0)
#: Width of one repeat of a silhouette, in pixels.
DISTANT_TILE_WIDTH = 64
#: Both layers stand on the collision line, so the ground never cuts a gap.
DISTANT_BASE_Y = GROUND_TOP

# --- Attract screen ---------------------------------------------------------

#: The title bird is the same sprite as the player, just scaled up, so there is
#: only ever one bird drawing code path.
TITLE_BIRD_SCALE = 3
TITLE_BIRD_X = SCREEN_WIDTH // 2
TITLE_BIRD_Y = 300
TITLE_TEXT_Y = 96
TITLE_BEST_Y = 400
TITLE_PROMPT_Y = 452
TITLE_HINT_Y = 486

#: The idle bob is a fixed table of whole-pixel offsets rather than a sine, so it
#: stays on the pixel grid and reads as a deliberate arcade hop.
IDLE_BOB_STEP_SECONDS = 0.17
IDLE_BOB_STEPS = (0, 1, 2, 3, 4, 5, 5, 4, 3, 2, 1, 0, -1, -2)

#: Fraction of each beat the start prompt is lit for. Below 1.0 so the prompt
#: blinks off rather than strobing on and off evenly.
PROMPT_VISIBLE_FRACTION = 0.75

# --- Bird animation ---------------------------------------------------------

BIRD_TILT_PER_VELOCITY = 0.09
BIRD_TILT_MIN_DEGREES = -70.0  # nose down, the steepest dive
BIRD_TILT_MAX_DEGREES = 25.0  # nose up, the highest climb
BIRD_TILT_STEPS = 10
BIRD_WING_FRAMES = 4
BIRD_WING_FRAMES_PER_SECOND = 9.0

# --- Bird sprite: pixel art -------------------------------------------------
#
# The bird is authored by hand on a small logical grid of BIRD_LOGICAL_SIZE
# pixels a side -- one character per pixel, see ``visuals`` -- and then scaled up
# by BIRD_PIXEL_SCALE with ``pygame.transform.scale``, which is nearest
# neighbour. Every visible pixel is therefore a hard BIRD_PIXEL_SCALE-square
# block: no smoothing, no anti-aliasing, no sub-pixel colours.
#
# BIRD_LOGICAL_SIZE * BIRD_PIXEL_SCALE == BIRD_SIZE, so the artwork is exactly
# as wide as the collision box. The scale is deliberately an integer; a
# fractional one would resample the grid and undo the whole point.

#: Pixels across the authored sprite, before scaling.
BIRD_LOGICAL_SIZE = 17
#: Real pixels per authored pixel. Integer, and an exact divisor of BIRD_SIZE.
#: Shared with the rest of the world so the bird sits on the same pixel grid.
BIRD_PIXEL_SCALE = PIXEL_SCALE
#: Logical pixels of empty canvas around the art, so a tilted pose still fits.
BIRD_PIXEL_MARGIN = 3
#: Where the authored wing grid is blitted, as (col, row) on the logical grid.
BIRD_WING_ORIGIN = (3, 8)

# --- Audio -------------------------------------------------------------------

#: Master volume in [0.0, 1.0], applied on top of the mute flag.
MASTER_VOLUME = 0.7

#: Small mono 16-bit format: cheap to generate, plenty for short arcade blips.
AUDIO_FREQUENCY = 22050
AUDIO_SIZE = -16
AUDIO_CHANNELS = 1
AUDIO_BUFFER = 512

#: Flap: a short bright upward blip.
FLAP_DURATION = 0.10
FLAP_START_HZ = 520.0
FLAP_END_HZ = 980.0
FLAP_GAIN = 0.85

#: Score: a two-tone chime rising a perfect fifth.
SCORE_DURATION = 0.16
SCORE_FIRST_HZ = 880.0
SCORE_SECOND_HZ = 1320.0
SCORE_TONE_SPLIT = 0.42
SCORE_GAIN = 0.55

#: Hit: a short filtered noise burst over a low thud.
HIT_DURATION = 0.14
HIT_START_HZ = 240.0
HIT_END_HZ = 90.0
HIT_GAIN = 0.50

#: Game over: three descending notes, C5 -> G4 -> D4.
GAME_OVER_DURATION = 0.55
GAME_OVER_NOTES = ((0.0, 523.25), (0.38, 392.0), (0.70, 293.66))
GAME_OVER_GAIN = 0.60
#: Silence baked in front of the jingle so it follows the impact instead of
#: landing on top of it. Pygame has no delayed-play call, so the gap is part of
#: the sound itself.
GAME_OVER_LEAD_IN = 0.14

# --- Game feel ---------------------------------------------------------------

#: The running score brightens briefly whenever a point is awarded.
SCORE_PULSE_SECONDS = 0.28
SCORE_PULSE_COLOR = (255, 214, 10)
#: Quantises the pulse so the text cache gains a bounded number of variants.
SCORE_PULSE_STEPS = 3

# --- Ground visuals ---------------------------------------------------------
#
# A green grass band over warm soil, both built from whole-pixel blocks on one
# 24-pixel repeat. ``GROUND_COLOR`` is the flat base of the grass: the row just
# above the soil is kept a single unbroken colour, so the band under the bird
# never flickers as the texture scrolls past.

GROUND_SOIL_COLOR = (198, 138, 78)
GROUND_SOIL_MARK_COLOR = (154, 100, 52)
#: Darker lip along the very top of the band, the classic grass edge.
GROUND_GRASS_EDGE_COLOR = (74, 132, 44)
GROUND_GRASS_EDGE_HEIGHT = 2
#: Blades poking up out of the base colour. Only ever drawn in the rows above
#: the last one, and never on the columns the width test samples, so the flat
#: base row and the coverage check both hold.
GROUND_GRASS_BLADE_COLOR = (92, 160, 52)
GROUND_GRASS_HEIGHT = 9
#: Columns of the repeat that carry a blade. One ``PIXEL_SCALE``-wide block each,
#: on even columns so they sit on the shared grid, and deliberately clear of the
#: columns the ground tests sample.
GROUND_BLADE_COLUMNS = (2, 4, 12, 20)
GROUND_TILE_WIDTH = 24
GROUND_MARK_WIDTH = 6
GROUND_SCROLL_SPEED = 120.0
#: Rows of the soil band that carry a pebble or a shadow, counting from the top
#: of the soil.
GROUND_PEBBLE_ROWS = (2, 5, 8)
