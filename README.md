# Flappy Bird

A minimal, modular [Pygame](https://www.pygame.org/) Flappy Bird.

Current status: the window, main loop, input handling, the bird's physics
(float position, gravity, flap, ceiling/ground detection), procedurally spawned
pipes (randomized gaps, timed spawning, off-screen recycling), bird/pipe
collision detection and scoring (one point per passed pipe plus a session high
score) are implemented. Graphics are drawn with plain Pygame shapes — no
external image or audio assets. Sounds and menus are intentionally left for
later phases.

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

## Collision

`collision.py` holds the only collision rules, so they can be tested without a
running game:

```python
check_pipe_collision(player, pipe)        # one pipe
check_any_pipe_collision(player, pipes)   # any pipe in a list
```

The bird's `Player.rect` is compared against `Pipe.top_rect` and
`Pipe.bottom_rect` with `pygame.Rect.colliderect` — no per-pixel checks.

**Boundary semantics** (standard Pygame behaviour): a collision needs a positive
overlap on *both* axes. Rectangles that merely share an edge or a corner do not
collide, so a hitbox resting exactly against a pipe edge still passes while one
pixel of penetration does not.

`Game.update` checks the player against the current pipes after both systems
have moved, and latches `game_over` on a hit — exactly as it already did for the
ceiling and the ground. While `game_over` is set, no further updates run, so the
bird and the pipes freeze where they collided.

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

`PipeManager` also takes optional `min_gap_center` / `max_gap_center`
arguments (defaulting to the settings above) so a caller — or a test — can pin
the gap range; the manager is otherwise identical to the configured behaviour.

## Scoring

`scoring.py` holds the only rule that awards points:

```python
count_newly_passed(player, pipes)   # -> int, how many pipes just went behind
```

A pipe counts as passed once it is **completely** behind the bird, meaning
`player.x > pipe.x + pipe.width` (`Pipe.has_behind`). Passing a pipe **body**
over the bird's column is therefore not enough, which is exactly the rule a
player perceives.

Exactly-once scoring relies on per-pipe state: each `Pipe` carries its own
`scored` flag (default `False`), and the helper flips it when it pays out. That
keeps the identity tied to the object, so three pipes that happen to share the
same `x` are still tracked independently, and a pipe that is recycled off-screen
is gone before it can be counted twice.

`Game.update(dt)` orders its checks deliberately:

1. `player.update(dt)` and `pipe_manager.update(dt)` move the world,
2. the ceiling/ground and pipe collision tests run — on a hit, `game_over` is
   latched and the method **returns immediately**,
3. only then does the game award newly passed pipes.

Because scoring is the last step, a crash on the same frame the bird clears a
pipe still pays nothing, while `game_over` freezes `score` until the next
`restart()`.

`Game.score` is the running score and `Game.high_score` the best of the current
process; both start at 0 and are plain writable attributes. `Game.add_score`
is the only mutator, and it raises the high score with `max()`. A restart clears
`score` but **keeps** `high_score`, so the best survives a crash; starting a
brand-new `Game` starts both counters from zero again.

The score is drawn with the built-in Pygame font at the top centre as
`Score: N`; after a game over a `Best: N` line appears underneath it.

## Run the tests

```bash
python -m pytest
```

The tests default to Pygame's headless `dummy` video driver, so they pass
without a display. They cover the settings and window configuration, the
player's gravity/jump behaviour, pipe geometry and spawning, every collision
edge case, the scoring rule (including exactly-once and the crash frame) and
the high-score lifecycle across restarts.

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
│       ├── collision.py         # bird/pipe hit tests
│       ├── scoring.py           # counts pipes passed exactly once
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
- `collision.py` owns the hit rules and has no state, so every edge case is
  testable without a window.
- `scoring.py` owns the payout rule; it reads and flips each pipe's own `scored`
  flag, so "one point per pipe" cannot drift from the pipe objects themselves.
- `Game` stays thin: it calls `player.update(dt)` and `pipe_manager.update(dt)`,
  asks `collision` whether the bird hit anything, awards what `scoring` reports
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

- Swap the placeholder shapes for real sprites and sound.

