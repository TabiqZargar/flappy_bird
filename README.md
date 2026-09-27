# Flappy Bird

A minimal, modular [Pygame](https://www.pygame.org/) Flappy Bird.

Current status: the window, main loop, input handling, the bird's physics
(float position, gravity, flap, ceiling/ground detection), procedurally spawned
pipes (randomized gaps, timed spawning, off-screen recycling), bird/pipe
collision detection, scoring (one point per passed pipe plus a session high
score), a progressive difficulty ladder driven by that score, and an explicit
start/play/game-over state machine are implemented. The look is layered on top: a
cached sky gradient, drifting parallax clouds, a scrolling textured ground, a
tilted animated bird and capped, lit pipes, all drawn with plain Pygame shapes
and the built-in font — no external image, font or audio assets. Four short
arcade sound effects are synthesised from scratch at start-up, and `M` mutes
them. Sounds are intentionally the only audio feature for now; there is no music.

The game starts exactly as the classic did and tightens very gently as you score:
a little faster, a little tighter, a little more often, up to a bounded maximum.

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
| `M`                | Toggle mute                               |
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

## Audio

`audio.py` owns every sound. There are no `.wav` or `.mp3` files: each effect is
synthesised from scratch into 16-bit PCM when the mixer opens, so there is
nothing to ship, load or fail to find.

| Effect      | Sound                                            | Fires when                       |
| ----------- | ------------------------------------------------ | -------------------------------- |
| `flap`      | short bright blip, pitch rising                  | a flap actually lifts the bird   |
| `score`     | two-tone chime rising a fifth                    | the score increases              |
| `hit`       | filtered noise burst over a falling low thud     | the round enters `GAME_OVER`     |
| `game_over` | three descending notes (C5 → G4 → D4)            | the round enters `GAME_OVER`     |

`Game` owns the one `AudioManager` and translates gameplay events into calls on
it — `audio.play_flap()`, `play_score()`, `play_hit()`, `play_game_over()`. No
other module imports `audio.py` or touches `pygame.mixer`; the player, pipes,
collision, scoring and visuals have no idea sound exists.

Each effect is generated once per process and the buffers are shared, so
starting another round never regenerates anything. The whole set is about 48 kB
and takes roughly 20 ms to build.

### Exactly one sound per event

Sounds hang off events, never off frame conditions:

- one flap → one `flap`, because `Game.flap` returns early outside `PLAYING`;
- a start or restart press is a flap, so it sounds once, not twice;
- one scoring event → one `score`, even if several pipes clear on the same frame
  (a chime per point would just stack into a noise burst);
- `Game.end_round()` is idempotent: it checks the state first, so the frozen
  game-over screen can never replay the crash, however many frames it renders.

### Mute and volume

`M` toggles mute in every state. It touches nothing but the audio manager, so it
cannot restart a round, move the bird or change the score.

```python
game.toggle_mute()      # -> new value
game.audio.muted        # -> bool
game.audio.toggle_mute()
```

Mute and volume are separate. `MASTER_VOLUME` (0.7) is the master level, clamped
to `[0.0, 1.0]` on the way in and pushed down to every sound when it changes;
`muted` is a boolean that stops sounds being played at all.

```python
game.audio.set_volume(0.4)   # clamped, so 5.0 -> 1.0 and -1.0 -> 0.0
```

### Headless and no-audio fallback

Audio is decoration, so it can never end a run. If the mixer will not open — no
sound card, a device another program is holding, a locked-down CI box — the
manager reports `available == False`, every play call becomes a no-op, and the
game plays on in silence. Every sound method swallows mixer errors, so an
unexpected Pygame build cannot crash the loop either.

`Game(headless=True)` skips the mixer entirely: nothing in an automated run
could hear it, and opening and closing a device per test is pure overhead. Audio
behaviour is tested with a fake mixer instead, so the suite never needs a sound
device.

The only format assumption is 16-bit signed PCM. If the mixer opens on anything
else, the manager stays silent rather than playing noise.

## Difficulty

The game gets harder as you score, gently and by a fixed amount. One level per
five points, six levels, and level 0 *is* the original game:

```
level = min(max(score, 0) // DIFFICULTY_SCORE_STEP, DIFFICULTY_MAX_LEVEL)

speed      = min(PIPE_SPEED  + level * 8.0,  160.0)   # 120 -> 160 px/s
gap        = max(PIPE_GAP_SIZE - level * 8,    120)   # 160 -> 120 px
interval   = max(PIPE_SPAWN_INTERVAL - level * 0.08, 1.2)   # 1.60 -> 1.20 s
```

| Level | From score | Speed | Gap | Interval |
| ----- | ---------- | ----- | --- | -------- |
| 0     | 0          | 120   | 160 | 1.60 s   |
| 1     | 5          | 128   | 152 | 1.52 s   |
| 2     | 10         | 136   | 144 | 1.44 s   |
| 3     | 15         | 144   | 136 | 1.36 s   |
| 4     | 20         | 152   | 128 | 1.28 s   |
| 5     | 25         | 160   | 120 | 1.20 s   |

The progression is **bounded**: level 5 is reached at 25 points and no score ever
makes the game harder again. The three clamps are the reason, and they are hit
exactly at the last level, so the caps are a guarantee rather than a coincidence.

It is also deliberately **subtle**. A full ladder is a 33% faster scroll and a
25% tighter gap — the hardest gap is still 3.5x the bird. Most runs end long
before the cap, so difficulty is something you feel rather than something you
see. Consecutive pipe pairs never overlap either: the spacing between them stays
at 192–196 px, comfortably wider than any gap, at every single level.

`difficulty.py` is a pure function of the score and nothing else — no clock, no
RNG, no game state. It only produces numbers; it never moves, spawns or draws
anything. There are just six possible answers, so they are built once at import
and `get_difficulty(score)` is a clamp and a tuple index.

```python
from flappy_bird import get_difficulty, all_profiles, BASELINE, MAXIMUM

get_difficulty(0)    # level 0, pipe_speed=120.0, pipe_gap=160, spawn_interval=1.6
get_difficulty(12)   # level 2, pipe_speed=136.0, pipe_gap=144, spawn_interval=1.44
get_difficulty(999)  # level 5, the same object every time, forever
get_difficulty(-5)   # level 0; a negative score cannot break the index
```

### Only future pipes are affected

Difficulty controls *when a pipe is born*, never a pipe that already exists. A
pipe copies the speed and gap off the profile at spawn and keeps them for its
whole life, so nothing in flight ever speeds up, tightens or changes shape
underneath you — and a pipe that just paid out a point cannot reshape itself in
the same frame.

That is why the update order in `Game.update` is fixed and deliberate:

```
pipes move and new ones spawn  ->  collision check  ->  scoring  ->  difficulty
```

A point earned on frame N is applied to the profile *after* that frame's pipes
are already on their way, so it first affects the next pipe to spawn. The same
ordering is what stops a scoring frame from being able to alter the collision
geometry of the pipe that caused it.

### What difficulty does not touch

The bird is exactly as it was. `GRAVITY`, `JUMP_VELOCITY` and `MAX_FALL_SPEED`
are never referenced by the difficulty code, and `tests/test_difficulty.py`
asserts that `player`, `collision`, `scoring`, `visuals` and `audio` do not
import the module or read a single `DIFFICULTY_*` setting. `BIRD_SIZE`,
`PIPE_WIDTH`, the ceiling and the ground are untouched as well — difficulty only
ever produces the three numbers a *new* pipe is built from.

### Restarts and frozen states

`PipeManager.reset()` puts the profile back to level 0 along with the pipes and
the spawn timer, so a restart is the original game again while the high score
carries over. The `START` attract screen and the `GAME_OVER` screen are frozen
worlds, so difficulty cannot advance in either: the start screen spawns no pipes
at all, and a game-over screen is never asked for a new profile.

The large-`dt` safeguards are unaffected. Whatever the difficulty, a 30-second
stall still spawns at most `MAX_SPAWNS_PER_UPDATE` pipes and discards the
leftover time, so there is no catch-up burst and no spawn debt.

A quiet `Difficulty N` readout sits under the score while playing, for anyone who
wants to watch the ladder climb.

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
`Player.rect`.

`test_audio.py` adds 101 tests over the sound effects and their wiring: the
shape of each generated buffer (length, no clipping, fades at both ends, the
right direction of pitch), safe initialisation against a working mixer, a
refusing mixer and a disabled manager, volume clamping, mute, and the fact that
no gameplay module imports `audio` or mentions `pygame.mixer`. The game's own
sound wiring is checked with a recording stand-in, so **no test needs a sound
device**.

`test_difficulty.py` adds 113 tests over the ladder and its plumbing: the level
boundaries, negative and huge scores, the clamps, monotonicity of all three
parameters, and the fairness invariant that consecutive pairs never overlap. The
integration half drives a live game to prove that a point never reshapes the pipe
that paid it, that pipes in flight keep their birth geometry, that new pipes pick
up the current profile, and that restart, `START` and `GAME_OVER` all behave.
Several of them read the modules' *syntax trees* rather than their text, so the
isolation guarantees cannot be defeated by a comment. `531 passed` at the time
of writing.

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
│       ├── settings.py          # all tunables (size, FPS, gravity, pipes, colors, audio, difficulty)
│       ├── audio.py             # AudioManager: generated effects, volume, mute
│       ├── visuals.py           # Visuals: sky, clouds, ground, bird sprite, caches
│       ├── difficulty.py        # DifficultyProfile: score -> pipe speed / gap / spawn interval
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
    ├── test_visuals.py
    ├── test_audio.py
    └── test_difficulty.py
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
- `audio.py` owns the sound, and is deliberately the most defensive module in
  the package: every entry point swallows mixer errors, because a broken sound
  device is not a reason to stop playing.
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

- Background music, and a settings screen for volume and difficulty.
- Replace the procedural bird with a sprite sheet, keeping `BirdSprite`'s
  cached-surface interface so nothing else has to change.

