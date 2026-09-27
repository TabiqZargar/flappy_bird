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
BIRD_WIDTH = 34
BIRD_HEIGHT = 24
BIRD_RADIUS = 12
BIRD_JUMP_VELOCITY = -380.0
BIRD_COLOR = (255, 214, 10)
BIRD_OUTLINE_COLOR = (60, 42, 0)

# --- Physics ----------------------------------------------------------------

GRAVITY = 1400.0
MAX_FALL_SPEED = 700.0
MAX_FRAME_TIME = 1.0 / 15.0

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
