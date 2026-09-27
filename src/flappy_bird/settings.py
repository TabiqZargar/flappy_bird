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

# --- Ground visuals ---------------------------------------------------------

GROUND_SOIL_COLOR = (198, 152, 104)
GROUND_SOIL_MARK_COLOR = (172, 126, 82)
GROUND_GRASS_EDGE_COLOR = (188, 146, 96)
GROUND_GRASS_EDGE_HEIGHT = 2
GROUND_GRASS_HEIGHT = 9
GROUND_TILE_WIDTH = 24
GROUND_MARK_WIDTH = 6
GROUND_SCROLL_SPEED = 120.0
