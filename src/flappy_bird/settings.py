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

GRAVITY = 1400.0
JUMP_VELOCITY = -520.0
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
PIPE_SPAWN_INTERVAL = 1.6
PIPE_COLOR = (34, 177, 76)
PIPE_EDGE_COLOR = (20, 105, 45)
PIPE_CAP_COLOR = (28, 152, 64)
PIPE_CAP_HEIGHT = 26
PIPE_HIGHLIGHT_COLOR = (108, 214, 138)
PIPE_SHADOW_COLOR = (16, 88, 40)
PIPE_HIGHLIGHT_WIDTH = 6
PIPE_SHADOW_WIDTH = 4

# --- Presentation -----------------------------------------------------------

BACKGROUND_COLOR = (233, 236, 239)
GROUND_COLOR = (222, 184, 135)
TEXT_COLOR = (54, 54, 54)
SCORE_FONT_SIZE = 28
SCORE_TEXT_Y = 100
BANNER_FONT_SIZE = 22
TITLE_FONT_SIZE = 46

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
CLOUD_BASE_WIDTH = 96
CLOUD_BASE_HEIGHT = 34
CLOUD_SURPLUS_X = 140  # how far past the right edge a recycled cloud returns

# --- Bird animation ---------------------------------------------------------

BIRD_TILT_PER_VELOCITY = 0.09
BIRD_TILT_MIN_DEGREES = -70.0  # nose down, the steepest dive
BIRD_TILT_MAX_DEGREES = 25.0  # nose up, the highest climb
BIRD_TILT_STEPS = 10
BIRD_WING_FRAMES = 4
BIRD_WING_FRAMES_PER_SECOND = 9.0
BIRD_WING_REST_DEGREES = -34.0
BIRD_WING_SWING_DEGREES = 66.0
BIRD_SPRITE_MARGIN = 10

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

GROUND_SOIL_COLOR = (198, 152, 104)
GROUND_SOIL_MARK_COLOR = (172, 126, 82)
GROUND_GRASS_EDGE_COLOR = (188, 146, 96)
GROUND_GRASS_EDGE_HEIGHT = 2
GROUND_GRASS_HEIGHT = 9
GROUND_TILE_WIDTH = 24
GROUND_MARK_WIDTH = 6
GROUND_SCROLL_SPEED = 120.0
