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
PIPE_GAP = 160
PIPE_SPEED = 120.0
PIPE_COLOR = (34, 177, 76)
PIPE_EDGE_COLOR = (20, 105, 45)
PIPE_MIN_EDGE = 60

# --- Presentation -----------------------------------------------------------

BACKGROUND_COLOR = (233, 236, 239)
GROUND_COLOR = (222, 184, 135)
TEXT_COLOR = (54, 54, 54)
SCORE_FONT_SIZE = 28
BANNER_FONT_SIZE = 22
