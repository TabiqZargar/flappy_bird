# Flappy Bird

A minimal, modular [Pygame](https://www.pygame.org/) Flappy Bird.

## Overview

One round of Flappy Bird in a window: flap the bird through the gaps, one point
per pipe, and the run gets gently harder the more you score. Everything is
generated in code — there is not a single image, font or audio file in the
repository.

The game starts exactly as the classic did and tightens very gently as you
score: a little faster, a little tighter, a little more often, up to a bounded
maximum.

## Features

- **Delta-time physics** — gravity, flap and terminal velocity integrated in
  seconds, so the game feels identical at any frame rate.
- **Explicit state machine** — `START` / `PLAYING` / `GAME_OVER`; only a live
  round simulates, so the other two are frozen worlds by construction.
- **Procedurally drawn world** — cached sky gradient, parallax clouds, scrolling
  textured ground, a tilted animated bird and capped, lit pipes, all from plain
  Pygame shapes and the built-in font.
- **Synthesised sound** — four short arcade effects generated into 16-bit PCM at
  start-up, with volume clamping and an `M` mute toggle. No music.
- **Progressive difficulty** — a six-level ladder driven by the score, bounded so
  no score ever makes the game harder again.
- **Score-based difficulty that only affects future pipes** — a pipe keeps the
  speed and gap it was born with, so nothing in flight changes underneath you.
- **Defensive audio** — a broken or missing sound device can never end a run.
- **Fully headless-testable** — the whole suite runs without a display or a sound
  device, and `Game(headless=True)` skips the mixer entirely.
- **Typed and packaged** — annotated sources, a PEP 561 `py.typed` marker, Ruff,
  mypy and a src layout that installs cleanly.

## Requirements

- Python 3.11 or newer
- Pygame, installed automatically with the package

## Installation

From the repository root:

```bash
python -m pip install -e .
```

That is the only command needed to play. It installs the one runtime dependency
(Pygame) and puts the `flappy_bird` package — which lives in `src/` — on the
import path, so no `PYTHONPATH` juggling is required afterwards.

To also install the development tools (pytest, Ruff, mypy and `build`) needed
for the [quality checks](#development-quality-checks) and
[packaging](#building-a-distribution):

```bash
python -m pip install -e ".[dev]"
```

`pyproject.toml` is the single source of truth for dependencies.
`requirements.txt` only defers to it (`-e .[dev]`), so the two cannot disagree.

A virtual environment is optional but recommended:

```bash
python -m venv .venv
```

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

## Running the game

```bash
python main.py
```

Two equivalent shortcuts, both using the same launcher:

```bash
python -m flappy_bird   # module entry point
flappy-bird            # console script, needs its scripts dir on PATH
```

`python -m flappy_bird` is the one to reach for if the console script is not on
your `PATH`; the module form works wherever the package is importable.

## Controls

| Key              | Action                                  |
| ---------------- | --------------------------------------- |
| `Space`/`Up`/`W` | Start, flap, or restart                 |
| Left mouse click | Start, flap, or restart                 |
| `M`              | Toggle mute                             |
| `R`              | Restart                                 |
| `Esc`            | Quit                                    |

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

## Progressive difficulty

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

## Running the tests

```bash
python -m pytest -q
```

`pyproject.toml` points `testpaths` at `tests/`, so this works from the
repository root with no path argument and no install step — the 531 tests are
found either way. `pytest -q` is the same thing if you prefer the console
script.

`test_game.py` holds 232 tests over the settings and window configuration, the
player's gravity/jump behaviour, pipe geometry and spawning, every collision edge
case, the scoring rule (including exactly-once and the crash frame), the
high-score lifecycle across restarts, and the state machine: the three states and
their transitions, that a frozen state really is frozen, per-key and per-button
input in every state, and each screen rendering the right text.

`test_visuals.py` adds 85 tests over the presentation layer: the sky gradient,
cloud layout and wrapping, the ground band and its fixed collision line, the tilt
curve and its clamps, wing animation from `dt`, the sprite caches, the panels
and the score text, pipe shading, and — importantly — that rendering and updating
the visuals never move the player, the pipes, the score or `Player.rect`.

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
waiting in `START`. Both live in `tests/conftest.py`, along with the helpers
more than one file needs (`advance`, `add_passed_pipe`, `crash` and the shared
`DT` frame step) in `tests/helpers.py` — so a fix to the scaffolding lands
everywhere at once. `test_audio.py` keeps its own `game`/`idle_game`, because
those swap in a recording stand-in for the audio manager.

## Development quality checks

Three checks, all configured in `pyproject.toml`, and all expected to pass
before a change lands:

```bash
ruff check src tests main.py   # lint
ruff format --check .          # formatting
mypy src                       # types
```

Those are the console scripts `pip install -e ".[dev]"` puts on your `PATH`. If
you would rather not depend on `PATH` — or you hit "command not found" because
the interpreter's scripts directory is missing from it — the exact equivalents
are:

```bash
python -m ruff check src tests main.py
python -m ruff format --check .
python -m mypy src
```

`ruff format` is the single formatter for the project — there is no second style
to reconcile with. The lint rule set is deliberately narrow (`E`, `F`, `I`, `B`):
it catches unused imports, undefined names, import order and obvious mistakes
without burying the code in style noise. Markdown is excluded from formatting so
the hand-aligned examples above keep their alignment.

mypy runs at a near-strict level, but Pygame ships no type information, so it is
the one thing configured as untyped. Where a module accepts something injected
rather than imported — the clock in `utils.frame_delta`, the mixer in
`AudioManager`, the player in `Visuals.draw_bird` — a small `Protocol` states
exactly what is needed instead of falling back to `Any` or a blanket ignore.

## Headless testing

The suite needs neither a display nor a sound device.

`tests/__init__.py` sets SDL to the `dummy` video and audio drivers before
anything else is imported, so `python -m pytest` works over SSH, in CI and in a
container with no graphics stack installed.

`Game(headless=True)` does the same thing for code under test: it defaults the
two SDL variables, forces the dummy drivers and builds the `AudioManager` with
`enabled=False`, so no device is opened at all. That is what the `game` and
`idle_game` fixtures use.

```python
from flappy_bird import Game

game = Game(headless=True)   # no window, no mixer
```

Audio is tested with a fake mixer and a recording stand-in for the game's own
manager, so the real device is never required. See
[Headless and no-audio fallback](#headless-and-no-audio-fallback) for what
happens when a real mixer is unavailable.

## Building a distribution

`build` ships in the `dev` extra, so after the install above:

```bash
python -m build
```

That produces both artifacts in `dist/`:

| File                                 | What it is                                            |
| ------------------------------------ | ----------------------------------------------------- |
| `flappy_bird-0.1.0-py3-none-any.whl` | the installable wheel                                 |
| `flappy_bird-0.1.0.tar.gz`            | the source distribution                                |

`python -m build` reads nothing from the environment, so it builds in isolation
and the wheel is produced *from* the sdist — the closest thing to what a user
will actually install. Both are named from the version in
`flappy_bird.__init__.py`, so they cannot drift from what the package reports.

The wheel holds the `flappy_bird` package, `py.typed` and `.dist-info`, and
nothing else. The sdist holds the sources, `README.md`, `pyproject.toml`,
`requirements.txt` and `MANIFEST.in`; `MANIFEST.in` keeps the test suite out of
it, because setuptools would otherwise pick up every `test_*.py` by default.
Both are pure `py3-none-any`: no compiled code, so one wheel serves every
platform and interpreter.

`build/` and `dist/` are generated, and are gitignored along with the caches.

## Architecture and project structure

```
flappy_bird/
├── main.py                      # entry point: builds and runs the Game
├── pyproject.toml               # packaging, metadata and tooling config
├── MANIFEST.in                  # what the source distribution includes
├── requirements.txt             # thin pointer to the project's own deps
├── README.md
├── .gitignore
├── src/
│   └── flappy_bird/
│       ├── __init__.py          # public API re-exports
│       ├── __main__.py          # `python -m flappy_bird` / the flappy-bird script
│       ├── py.typed             # PEP 561 marker: the package ships its types
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
    ├── conftest.py              # shared fixtures: game, idle_game
    ├── helpers.py               # shared helpers: DT, advance, add_passed_pipe, crash
    ├── test_game.py
    ├── test_visuals.py
    ├── test_audio.py
    └── test_difficulty.py
```

Generated directories — `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`,
`.mypy_cache/`, `build/`, `dist/`, `*.egg-info/` and `.venv/` — are not part of
the project and are covered by `.gitignore`.

The package is a standard [src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/):
the importable code lives in `src/`, never at the repository root, so there is
exactly one copy of it on the import path whether it was installed or not.

## Configuration and customization

Every tunable value in the game is a module-level constant in
`src/flappy_bird/settings.py`. There is no config file and no settings screen:
you change a number, restart, and that is the whole mechanism. Constants are
grouped by what they affect. (The only environment variables the package reads
are `SDL_VIDEODRIVER` and `SDL_AUDIODRIVER`, and only in the `headless=True`
path described in [Headless testing](#headless-testing).)

| Group                                   | Examples                                                     |
| --------------------------------------- | ------------------------------------------------------------ |
| Window and loop                         | `SCREEN_WIDTH`, `SCREEN_HEIGHT`, `FPS`, `CAPTION`            |
| Bird physics and geometry               | `GRAVITY`, `JUMP_VELOCITY`, `MAX_FALL_SPEED`, `BIRD_SIZE`    |
| Boundaries                              | `CEILING_Y`, `GROUND_HEIGHT`, `GROUND_TOP` (derived)         |
| Pipes                                   | `PIPE_SPEED`, `PIPE_GAP_SIZE`, `PIPE_WIDTH`, spawn interval  |
| Difficulty ladder                       | `DIFFICULTY_SCORE_STEP`, `DIFFICULTY_MAX_LEVEL`, the clamps  |
| Colours                                 | `BIRD_*_COLOR`, `PIPE_*_COLOR`, `SKY_*_COLOR`, `CLOUD_*`     |
| Text and layout                         | `SCORE_FONT_SIZE`, `TITLE_FONT_SIZE`, `*_TEXT_Y`             |
| Audio                                   | `MASTER_VOLUME`, `AUDIO_FREQUENCY`, per-effect gains and pitch |
| Sprite animation                        | `BIRD_TILT_*`, `BIRD_WING_*`, `BIRD_SPRITE_MARGIN`          |
| World motion                            | `CLOUD_*`, `GROUND_SCROLL_SPEED`, `CLOUD_SURPLUS_X`          |

A few things worth knowing before editing:

- **`GROUND_TOP` is derived** (`SCREEN_HEIGHT - GROUND_HEIGHT`). Change
  `SCREEN_HEIGHT` and the ground follows; editing `GROUND_TOP` directly is
  overwritten on the next line.
- **Difficulty clamps must be reachable.** The ladder is built once at import
  from `PIPE_SPEED`, `PIPE_GAP_SIZE` and `PIPE_SPAWN_INTERVAL`, so level 0 always
  equals those three constants. If a `DIFFICULTY_*` clamp is set so the last
  level is never actually reached, the cap is simply never hit — the progression
  stays monotonic, but the documented maximum is wrong. `tests/test_difficulty.py`
  asserts the clamp boundaries, so it will tell you.
- **Colours are plain `(r, g, b)` tuples**, accepted anywhere a Pygame colour is.
- **Audio is synthesised from these numbers.** `AUDIO_FREQUENCY`, `AUDIO_SIZE`
  and `AUDIO_CHANNELS` describe the format the mixer is asked for; if it hands
  back anything other than 16-bit PCM the game plays on in silence rather than
  noise.

`PipeManager` also takes optional overrides for tests and experiments — `speed`,
`gap`, `spawn_interval` and the gap-center range. Passing any of them pins that
manager to fixed values instead of following the difficulty ladder.

## Design notes

- `main.py` only initialises and runs `Game`; all logic lives in the package.
- Dependencies are declared exactly once, in `pyproject.toml`; `requirements.txt`
  just defers to it, so the two can never disagree.
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

