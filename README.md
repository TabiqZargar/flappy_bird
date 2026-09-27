# Flappy Bird

A minimal, modular [Pygame](https://www.pygame.org/) Flappy Bird.

Current status: the window, main loop, input handling, the bird's physics
(float position, gravity, flap, ceiling/ground detection) and procedurally
spawned pipes (randomized gaps, timed spawning, off-screen recycling) are
implemented. Graphics are drawn with plain Pygame shapes — no external image or
audio assets. Pipe/player collision, scoring, sounds and menus are intentionally
left for later phases.

## Requirements

- Python 3.11 or newer
- The packages in `requirements.txt` (Pygame, pytest)

## Install

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

Then install the dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run the game

The game code lives in `src/`, so `src` must be on the import path:

```bash
# macOS / Linux
PYTHONPATH=src python main.py

# Windows (PowerShell)
$env:PYTHONPATH = "src"; python main.py
```

### Controls

| Key                | Action        |
| ------------------ | ------------- |
| `Space`/`Up`/`W`   | Flap upwards  |
| Left mouse click   | Flap upwards  |
| `R`                | Restart       |
| `Esc`              | Quit          |

## Physics

All movement is integrated against a delta time in seconds, so the game feels
identical at any frame rate. The tunables live in `src/flappy_bird/settings.py`:

| Constant            | Value     | Meaning                                    |
| ------------------- | --------- | ------------------------------------------ |
| `GRAVITY`           | `1400.0`  | Downward acceleration in px/s²             |
| `JUMP_VELOCITY`     | `-520.0`  | Upward velocity (px/s) set on each flap    |
| `MAX_FALL_SPEED`    | `750.0`   | Terminal downward velocity in px/s         |
| `BIRD_SIZE`         | `34`      | Bird hitbox size in px                     |
| `CEILING_Y`         | `0`       | Top of the playable area                   |
| `GROUND_TOP`        | `680`     | Ground line (`SCREEN_HEIGHT - GROUND_HEIGHT`) |

A flap **assigns** `velocity_y` instead of adding to it, so mashing the key can
never build up a runaway speed. The player exposes `hit_ceiling` and
`hit_ground`; `Game.update` latches `game_over` when either becomes true.

## Pipes

`PipeManager` owns spawning, timing and recycling; `Pipe` owns only its own
geometry and horizontal movement. Every manager tick:

1. moves each pipe left by `speed * dt`,
2. drops the pipes that are completely off-screen (via a new list, never while
   iterating the live one),
3. emits any pipe the spawn timer owes.

| Constant                 | Value  | Meaning                                    |
| ------------------------ | ------ | ------------------------------------------ |
| `PIPE_SPEED`             | `120.0`| Horizontal speed in px/s                   |
| `PIPE_SPAWN_INTERVAL`    | `1.6`  | Seconds between pipes                      |
| `PIPE_GAP_SIZE`          | `160`  | Height of the passable gap in px           |
| `PIPE_MIN_GAP_CENTER`    | `160`  | Lowest allowed gap center                  |
| `PIPE_MAX_GAP_CENTER`    | `540`  | Highest allowed gap center                 |
| `PIPE_WIDTH`             | `60`   | Width of one pipe column in px             |

`PIPE_SPAWN_INTERVAL * PIPE_SPEED` (192 px) is the distance between consecutive
pipes, so the gap always stays reachable.

Gap centers come from `utils.random_gap_center`, which narrows the configured
range further if needed so the whole gap can never land outside the playable
area. A pipe spans the ceiling down to its gap, and from its gap down to the
ground, which the ground band then draws over.

Spawning is capped at `PipeManager.MAX_SPAWNS_PER_UPDATE` (3) per tick, so a
long stall or a debugger pause cannot flood the screen with pipes; the leftover
timer debt is dropped instead of accumulating.

## Run the tests

```bash
python -m pytest
```

The tests default to Pygame's headless `dummy` video driver, so they pass
without a display. They check the settings and window configuration, the
player's gravity/jump behaviour and the pipe geometry.

## Project structure

```
flappy_bird/
├── main.py                      # entry point: builds and runs the Game
├── requirements.txt
├── README.md
├── src/
│   └── flappy_bird/
│       ├── __init__.py          # public API re-exports
│       ├── game.py              # Game: window, main loop, input, update, render
│       ├── settings.py          # all tunables (size, FPS, gravity, pipes, colors)
│       ├── player.py            # Player: position, velocity, flap, draw
│       ├── pipe.py              # Pipe: gap geometry, horizontal movement, draw
│       ├── pipe_manager.py      # PipeManager: spawn timing, pipe list, recycling
│       └── utils.py             # small helpers (clamp, frame delta, layout)
└── tests/
    ├── __init__.py              # adds src/ to sys.path, headless SDL
    └── test_game.py
```

## Design notes

- `main.py` only initialises and runs `Game`; all logic lives in the package.
- `Player` owns its own physics (position, velocity, boundaries) and knows
  nothing about the game loop, pipes or rendering order.
- `Pipe` owns geometry and movement; `PipeManager` owns *when* pipes exist. The
  manager is injected with an `rng`, so tests can make spawning deterministic.
- `Game` stays thin: it calls `player.update(dt)` and `pipe_manager.update(dt)`
  and draws what the manager holds. `Game.pipes` is a read-only view of the
  manager's live list.
- Every tunable value is a constant in `settings.py`.
- `Game` exposes `handle_events()`, `update(dt)` and `render()` separately from
  `run()`, so individual stages can be driven in tests.
- `update()` is driven by a delta-time in seconds (clamped via
  `utils.frame_delta`) instead of per-frame constants, so physics stays
  frame-rate independent.
- `Game(headless=True)` forces the dummy SDL drivers for automated runs.

## Next steps

- Add collision detection between `Player.rect` and each `Pipe.rects`.
- Increment the score when a pipe is passed (`Pipe.has_behind`).
- Swap the placeholder shapes for real sprites and sound.
