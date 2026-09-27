# Flappy Bird

A minimal, modular [Pygame](https://www.pygame.org/) Flappy Bird.

Current status: the window, main loop, input handling, the bird's physics
(float position, gravity, flap, ceiling/ground detection), procedurally spawned
pipes (randomized gaps, timed spawning, off-screen recycling), bird/pipe
collision detection, scoring (one point per passed pipe plus a session high
score) and an explicit start/play/game-over state machine are implemented.
The look is layered on top: a cached sky gradient, drifting parallax clouds, a
scrolling textured ground, a tilted animated bird and capped, lit pipes, all
drawn with plain Pygame shapes and the built-in font — no external image, font
or audio assets. Sounds are intentionally left for a later phase.

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

| Key                | Action                                    |
| ------------------ | ----------------------------------------- |
| `Space`/`Up`/`W`   | Start, flap, or restart                   |
| Left mouse click   | Start, flap, or restart                   |
| `R`                | Restart                                   |
| `Esc`              | Quit                                      |

Right and middle mouse buttons are ignored in every state.

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
`hit_ground`.

## Game states

`state.py` defines the whole lifecycle as one enum:

```python
GameState.START      # attract screen, frozen world
GameState.PLAYING    # the live round
GameState.GAME_OVER  # round ended, frozen world
```

`Game.state` is the single source of truth. It drives three decisions — whether
`update()` simulates, what a press of the flap key means, and which screen gets
drawn:

| From        | Input                             | Result                             |
| ----------- | --------------------------------- | ---------------------------------- |
| `START`     | `Space` / `Up` / `W` / left click | `PLAYING`                          |
| `PLAYING`   | `Space` / `Up` / `W` / left click | flap the bird                      |
| `PLAYING`   | pipe hit, ceiling or ground       | `GAME_OVER`                        |
| `GAME_OVER` | `Space` / `Up` / `W` / left click | `PLAYING` with the score back to 0 |
| any         | `Esc`                             | quit                               |

There is no Start or Restart button: the same press that starts the game also
lifts the bird, so the player never has to click twice to get off the ground.
`R` still restarts from anywhere, as before.

Only `PLAYING` advances the simulation, so `START` and `GAME_OVER` are frozen
worlds by construction rather than by scattered flags: no physics, no pipe
movement, no spawning and no scoring can happen outside a live round. A new
`Game` begins in `START` with `score = 0` and `high_score = 0`.

`Game.game_over` is kept as a read/write property over `state` for
compatibility, but nothing in the game reads it any more.

### Reset semantics

Two methods keep "what a round owns" separate from "what a session owns":

- `reset_round()` — player, pipes, spawn timer, `score` and the per-pipe
  scoring flags (which go away with the pipes that carried them), then
  `state = PLAYING`.
- `start_round()` — the public entry point for a start/restart press; it calls
  `reset_round()`.

`high_score` is **not** touched by either, so the best of the session survives
every restart. Only a brand-new `Game` instance starts it back at zero.

### Screens

`render()` draws the shared world and then dispatches to one small method per
state, so no single method grows a nest of conditionals:

| Method                  | Draws                                                       |
| ----------------------- | ----------------------------------------------------------- |
| `render_world()`        | sky, clouds, pipes, bird, ground (shared by every state)     |
| `render_start_screen()` | `FLAPPY BIRD` + `Press SPACE or Click to Start`             |
| `render_playing()`      | the running `Score: N`                                      |
| `render_game_over()`    | `GAME OVER`, `Score: N`, `Best: N`, `Press SPACE or Click to Restart` |

The bird and the world stay visible underneath the panels, and every panel is
sized to its own text and centred, so the prompts never overlap the score.
Panel surfaces are cached per (title, lines) pair, so the cards are rasterised
once instead of on every frame.

## Visuals

`visuals.py` owns the entire look of the game. It reads state and an explicit
`dt`, and it never writes gameplay: it has no reference to the player, the
pipes, the score or the collision rules, so nothing it draws can change how the
game plays.

`Game` owns one `Visuals` and advances it once per `update(dt)`, before the
early return for non-playing states:

```python
self.visuals.update(
    dt,
    animate_bird=self.state.is_playing,
    drift_clouds=self.state is not GameState.GAME_OVER,
)
```

That single call decides the whole ambient-motion policy:

| State      | Bird wing/tilt animation | Clouds + ground scroll |
| ---------- | ------------------------ | ---------------------- |
| `START`    | frozen                   | drifting               |
| `PLAYING`  | running                  | drifting               |
| `GAME_OVER`| frozen                   | frozen                 |

The attract screen is therefore alive rather than static, the game-over screen
freezes completely behind its panel, and the gameplay rules stay untouched.

### The bird

`BirdSprite` draws the bird out of ellipses and polygons — body, belly, wing
with two feather stripes, eye with pupil, beak and tail — and gives it two
independent motions:

- **Tilt** from vertical velocity: rising lifts the nose, falling drops it,
  clamped to `BIRD_TILT_MIN_DEGREES`/`BIRD_TILT_MAX_DEGREES`, and quantised into
  `BIRD_TILT_STEPS` buckets so a smooth curve does not rebuild a surface on
  every micro-change of velocity.
- **Wing** from an accumulated `wing_phase` driven by `dt`, cycling through
  `BIRD_WING_FRAMES` raised/lowered positions at `BIRD_WING_FPS`.

Each `(tilt, wing)` pair is rendered once into a surface and cached, so at most
`BIRD_TILT_STEPS * BIRD_WING_FRAMES` bird surfaces exist, no matter how long the
game runs. The canvas carries a small margin so a rotated bird is never clipped.

**Rotation is visual only.** `Player.rect` is still the same axis-aligned
`BIRD_SIZE` square that collision uses, so the hitbox is bit-for-bit the hitbox
it has always been. The drawn body is `BIRD_SIZE` either way; tilting only
enlarges the transparent canvas around it.

`Player.draw()` simply delegates to the shared default sprite, so a bare
`Player` still draws itself without a `Game`.

### World layers

`render_world()` draws back to front: sky, clouds, pipes, bird, ground.

- **Sky** — a `build_sky` vertical gradient, rasterised once and blitted.
- **Clouds** — `CloudField` holds layered clouds that wrap around the screen as
  they drift, at different speeds per layer for parallax. It takes an `rng`, so
  a test can pin the layout.
- **Ground** — `GroundBand` scrolls a tiled strip of grass plus soil marks. The
  scroll is pure texture: the collision line stays exactly at `GROUND_TOP`, and
  the grass edge stays pinned while only the pattern moves.
- **Pipes** — `Pipe.draw()` adds a cap at the end facing the gap, a vertical
  highlight, a shadow and an outline, all drawn *inside* `top_rect` and
  `bottom_rect`. A pipe can therefore never look larger than it collides, and
  the gap always reads as a gap.

### Caching

Nothing expensive is rebuilt per frame:

| Cache          | Key                        | Bounded by                    |
| -------------- | -------------------------- | ----------------------------- |
| `Visuals.sky`  | built once                 | 1 surface                     |
| `BirdSprite`   | `(tilt_index, wing_index)` | `TILT_STEPS * WING_FRAMES`    |
| `TextCache`    | text + font                | one per distinct label        |
| `PanelCache`   | title + lines              | `MAX_PANELS` (24), LRU-ish    |

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
have moved, and moves to `GAME_OVER` on a hit — exactly as it already did for
the ceiling and the ground. While the state is `GAME_OVER`, no further updates
run, so the bird and the pipes freeze where they collided.

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
2. the ceiling/ground and pipe collision tests run — on a hit, the state becomes
   `GAME_OVER` and the method **returns immediately**,
3. only then does the game award newly passed pipes.

Because scoring is the last step, a crash on the same frame the bird clears a
pipe still pays nothing, and the `GAME_OVER` state freezes `score` until the
next `start_round()`.

`Game.score` is the running score and `Game.high_score` the best of the current
process; both start at 0 and are plain writable attributes. `Game.add_score`
is the only mutator, and it raises the high score with `max()`. A restart clears
`score` but **keeps** `high_score`, so the best survives a crash; starting a
brand-new `Game` starts both counters from zero again.

The score is drawn with the built-in Pygame font at the top centre as
`Score: N`; the game-over panel repeats it next to the `Best: N` line.

## Run the tests

```bash
python -m pytest
```

The tests default to Pygame's headless `dummy` video driver, so they pass
without a display. They cover the settings and window configuration, the
player's gravity/jump behaviour, pipe geometry and spawning, every collision
edge case, the scoring rule (including exactly-once and the crash frame), the
high-score lifecycle across restarts, and the state machine: the three states
and their transitions, that a frozen state really is frozen, per-key and
per-button input in every state, and each screen rendering the right text.

`test_visuals.py` adds 85 tests over the presentation layer: the sky gradient,
cloud layout and wrapping, the ground band and its fixed collision line, the
tilt curve and its clamps, wing animation from `dt`, the sprite caches, the
panels and the score text, pipe shading, and — importantly — that rendering and
updating the visuals never move the player, the pipes, the score or
`Player.rect`. `317 passed` at the time of writing.

Two fixtures model the two situations: `game` is a round already in progress
(what the gameplay tests drive), and `idle_game` is a fresh instance still
waiting in `START`.

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
│       ├── visuals.py           # Visuals: sky, clouds, ground, bird sprite, caches
│       ├── player.py            # Player: position, velocity, flap, draw
│       ├── pipe.py              # Pipe: gap geometry, horizontal movement, draw
│       ├── pipe_manager.py      # PipeManager: spawn timing, pipe list, recycling
│       ├── collision.py         # bird/pipe hit tests
│       ├── scoring.py           # counts pipes passed exactly once
│       ├── state.py             # GameState: the start/play/game-over lifecycle
│       └── utils.py             # small helpers (clamp, frame delta, layout)
└── tests/
    ├── __init__.py              # adds src/ to sys.path, headless SDL
    ├── test_game.py
    └── test_visuals.py
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
- `state.py` owns the lifecycle vocabulary, so nothing else has to invent a
  string or a boolean to mean "the round is over".
- `visuals.py` owns the look, and is the only module that both reads the state
  and holds caches. Because it cannot reach the player or the pipes, art changes
  are structurally incapable of altering the physics or the hitboxes.
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

- Add sound (flap, score, hit) — still the only missing subsystem.
- Replace the procedural bird with a sprite sheet, keeping `BirdSprite`'s
  cached-surface interface so nothing else has to change.

