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
- **Procedurally drawn pixel-art world** — a banded sky, two layers of parallax
  distant scenery, block-built clouds, a scrolling grass-and-soil ground, capped
  and lit pipes, and every label rasterised through a hand-authored 5×7 bitmap
  font. No smoothing anywhere: each authored pixel becomes a hard square.
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
| `GRAVITY`           | `1250.0`  | Downward acceleration in px/s²             |
| `JUMP_VELOCITY`     | `-370.0`  | Upward velocity (px/s) set on each flap    |
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
| `render_world()`        | sky, scenery, clouds, pipes, bird, ground (shared by every state) |
| `render_start_screen()` | `FLAPPY BIRD`, a large idle bird, `Best: N`, a blinking `Press SPACE or Click to Start`, and the control hints |
| `render_playing()`      | the running `Score: N` and the difficulty level              |
| `render_game_over()`    | `GAME OVER`, `Score: N`, `Best: N`, `Press SPACE or Click to Restart` |

The start screen is deliberately **not** a card: the bird and the world sit
behind real UI, so the title screen is the game rather than a menu drawn on top
of it. The bird is passed through as a hero sprite (`render_world(show_bird=False)`
plus `draw_title_bird()`), so the attract screen shows one big flapping bird
instead of two, and the small one keeps its gameplay position.

The bird and the world stay visible underneath the game-over panel, and every
panel is sized to its own text and centred, so the prompts never overlap the
score. Panel surfaces are cached per (title, lines) pair, so the cards are
rasterised once instead of on every frame.

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
    animate_bird=not frozen,
    drift_clouds=not frozen,
)
```

That single call decides the whole ambient-motion policy:

| State      | Bird wing/tilt + idle bob | Clouds, scenery, ground scroll |
| ---------- | -------------------------- | ------------------------------ |
| `START`    | running                   | drifting                       |
| `PLAYING`  | running                   | drifting                       |
| `GAME_OVER`| frozen                    | frozen                         |

The attract screen is therefore alive rather than static, the game-over screen
freezes completely behind its panel, and the gameplay rules stay untouched. The
wing beat runs on `START` too: there is no velocity to tilt against before the
round begins, so a flapping wing is the only life the sprite can have there.

Everything the attract screen animates is a pure accumulator driven by `dt` —
`idle_phase` for the bob, `prompt_visible` for the blink, the layer offsets for
the scroll. None of it is a wall clock, so the animation is deterministic and
pausing the loop cannot desynchronise it from the world.

### The bird

`BirdSprite` is pixel art, not a smooth drawing. The bird is written out in
`visuals.py` as text, one character per authored pixel — a 17×17 body with
belly, eye, pupil, beak, tail, highlight and shadow, plus four 6×3 wing poses —
and each character maps to a colour in `BIRD_PALETTE`. The grid is painted onto a
small logical canvas with a 3-pixel margin, rotated for the tilt, and then scaled
up by `BIRD_PIXEL_SCALE` with `pygame.transform.scale`. Scaling is nearest
neighbour, so every authored pixel becomes a hard 2×2 square: no smoothing, no
anti-aliasing, and not a single colour outside the palette. `smoothscale` would
blend the palette into new colours, which is exactly what the pixel art must
never do. `BIRD_LOGICAL_SIZE * BIRD_PIXEL_SCALE == BIRD_SIZE`, so the artwork is
as wide as the collision box.

On top of that it has two independent motions:

- **Tilt** from vertical velocity: rising lifts the nose, falling drops it,
  clamped to `BIRD_TILT_MIN_DEGREES`/`BIRD_TILT_MAX_DEGREES`, and quantised into
  `BIRD_TILT_STEPS` buckets so a smooth curve does not rebuild a surface on
  every micro-change of velocity.
- **Wing** from an accumulated `wing_phase` driven by `dt`, cycling through
  `BIRD_WING_FRAMES` poses at `BIRD_WING_FRAMES_PER_SECOND`. The wing is stamped
  over the body below the eye, so the bird keeps its face in every frame.

Each `(tilt, wing)` pair is rendered once into a surface and cached, so at most
`BIRD_TILT_STEPS * BIRD_WING_FRAMES` bird surfaces exist, no matter how long the
game runs. The margin is there so a rotated bird is never clipped, and it
costs nothing: the extra canvas is transparent.

**Rotation is visual only.** `Player.rect` is still the same axis-aligned
`BIRD_SIZE` square that collision uses, so the hitbox is bit-for-bit the hitbox
it has always been. The drawn body is `BIRD_SIZE` either way; tilting only
enlarges the transparent canvas around it.

`Player.draw()` simply delegates to the shared default sprite, so a bare
`Player` still draws itself without a `Game`.

### World layers

`render_world()` draws back to front: sky, distant scenery, clouds, pipes, bird,
ground. The order is the layering contract — anything listed later covers
anything listed earlier, and every layer is painted only inside its own bounds.

- **Sky** — `build_sky` paints `SKY_BAND_COUNT` (12) flat horizontal bands that
  step from `SKY_TOP_COLOR` to `SKY_BOTTOM_COLOR`. The bands are deliberately
  hard-edged rather than a smooth gradient: a smooth ramp invents hundreds of
  in-between colours, which breaks the palette and reads as anti-aliasing. The
  surface is rasterised once and blitted. The exact top and bottom colours are
  pinned, so the horizon still reads as a gradient.
- **Distant scenery** — `SceneryField` stacks two `SceneryLayer`s (far, near)
  generated from `DISTANT_PROFILES`, a compact column-height description. Each
  layer bakes a seamless tile once and scrolls it at its own speed, so the hills
  and blocks behind the clouds move at different rates. Both end flush with
  `GROUND_TOP`, so the parallax lands on the horizon rather than floating.
- **Clouds** — `CloudField` holds clouds built from `CLOUD_PROFILE`, a column of
  heights expanded into whole blocks of `CLOUD_BLOCK_PER_SCALE` pixels. Blocks
  are whole and a whole number of pixels wide, so a cloud is a staircase of
  squares — never a soft blob, never a half-pixel edge. Clouds wrap around the
  screen as they drift, and the field takes an `rng`, so a test can pin the
  layout and get the same frame every time.
- **Ground** — `GroundBand` scrolls a tiled strip: a dark grass lip, a flat grass
  band, blades and pebbles in the soil below it. The scroll is pure texture: the
  collision line stays exactly at `GROUND_TOP`, and the flat grass row is
  guaranteed single-coloured so the ground never looks striped.
- **Pipes** — `Pipe.draw()` adds a cap at the end facing the gap, a vertical
  highlight, a shadow and an outline, all drawn *inside* `top_rect` and
  `bottom_rect`. A pipe can therefore never look larger than it collides, and
  the gap always reads as a gap.

### Text

`pixelfont.py` holds a hand-authored 5×7 bitmap font — the letters, digits and
punctuation the game actually uses, written out as strings where `#` is ink.
Rendering paints each `#` as a `scale`-sized rectangle, so a label is hard-edged
at every zoom level and cannot drift off the palette the way an antialiased
system font does.

It sits behind the same interface as the smooth Pygame renderer
(`render`/`measure`, via a small `Labeler` `Protocol`), so `TextCache` and
`PanelCache` do not care which back-end they are handed. That is what lets a
test pass a bare `pygame.font.Font` while the game draws its own pixel text.

### Caching

Nothing expensive is rebuilt per frame:

| Cache            | Key                                  | Bounded by                    |
| ---------------- | ------------------------------------ | ----------------------------- |
| `Visuals.sky`    | built once                           | 1 surface                     |
| `BirdSprite`     | `(tilt_index, wing_index)`           | `TILT_STEPS * WING_FRAMES`    |
| `SceneryLayer`   | built once per layer                 | 1 tile each                   |
| `GroundBand`     | built once                           | 1 tile                        |
| `PixelFont`      | text + scale + colours               | `max_entries` (256), LRU-ish  |
| `TextCache`      | text + font                          | one per distinct label        |
| `PanelCache`     | title + lines + fonts + colour       | `MAX_PANELS` (24), LRU-ish    |

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
interval   = max(PIPE_SPAWN_INTERVAL - level * 0.08, 1.6)   # 2.00 -> 1.60 s
```

| Level | From score | Speed | Gap | Interval |
| ----- | ---------- | ----- | --- | -------- |
| 0     | 0          | 120   | 160 | 2.00 s   |
| 1     | 5          | 128   | 152 | 1.92 s   |
| 2     | 10         | 136   | 144 | 1.84 s   |
| 3     | 15         | 144   | 136 | 1.76 s   |
| 4     | 20         | 152   | 128 | 1.68 s   |
| 5     | 25         | 160   | 120 | 1.60 s   |

The progression is **bounded**: level 5 is reached at 25 points and no score ever
makes the game harder again. The three clamps are the reason, and they are hit
exactly at the last level, so the caps are a guarantee rather than a coincidence.

It is also deliberately **subtle**. A full ladder is a 33% faster scroll and a
25% tighter gap — the hardest gap is still 3.5x the bird. Most runs end long
before the cap, so difficulty is something you feel rather than something you
see. Consecutive pipe pairs never overlap either: the spacing between them stays
at 240–256 px, comfortably wider than any gap, at every single level.

`difficulty.py` is a pure function of the score and nothing else — no clock, no
RNG, no game state. It only produces numbers; it never moves, spawns or draws
anything. There are just six possible answers, so they are built once at import
and `get_difficulty(score)` is a clamp and a tuple index.

```python
from flappy_bird import get_difficulty, all_profiles, BASELINE, MAXIMUM

get_difficulty(0)    # level 0, pipe_speed=120.0, pipe_gap=160, spawn_interval=2.0
get_difficulty(12)   # level 2, pipe_speed=136.0, pipe_gap=144, spawn_interval=1.84
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
| `PIPE_SPAWN_INTERVAL`    | `2.0`  | Seconds between pipes                      |
| `PIPE_GAP_SIZE`          | `160`  | Height of the passable gap in px           |
| `PIPE_MIN_GAP_CENTER`    | `160`  | Lowest allowed gap center                  |
| `PIPE_MAX_GAP_CENTER`    | `540`  | Highest allowed gap center                 |
| `PIPE_WIDTH`             | `60`   | Width of one pipe column in px             |

`PIPE_SPAWN_INTERVAL * PIPE_SPEED` (240 px) is the distance between consecutive
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

The score is drawn with the bitmap pixel font at the top centre as `Score: N`,
with a `Difficulty N` line beneath it; the game-over panel repeats the score
next to the `Best: N` line, and the title screen shows the best too.

## Running the tests

```bash
python -m pytest -q
```

`pyproject.toml` points `testpaths` at `tests/`, so this works from the
repository root with no path argument and no install step — the 671 tests are
found either way. `pytest -q` is the same thing if you prefer the console
script.

| Module              | Tests | Covers                                                                                                                                  |
| ------------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `test_game.py`      | 275   | settings and window configuration, physics, pipe geometry and spawning, collision edge cases, scoring, high scores, the state machine, input in every state, and each screen |
| `test_visuals.py`   | 151   | banded sky, block clouds, parallax scenery, ground artwork, the tilt curve, wing and idle animation, every cache, panel and pipe shading      |
| `test_audio.py`     | 101   | the shape of each generated buffer, safe init against working/refusing/disabled mixers, volume clamping and mute                           |
| `test_difficulty.py`| 113   | level boundaries, the clamps, monotonicity, and that a point never reshapes the pipe that paid it                                        |
| `test_pixelfont.py` | 31    | glyph geometry, hard-block scaling, shadows, measurement and the bounded cache                                                          |

Several things in there are worth calling out, because they are the tests that
would actually catch a regression:

- **The world cannot touch the simulation.** The visuals suite asserts that
  advancing and rendering `Visuals` never moves the player, the pipes, the score
  or `Player.rect`, and the game suite repeats it for a real `Game` — including
  600 frames of attract screen, where the decoration must be provably moving
  (`len(set(offsets)) > 1`) while the simulation is provably still.
- **The palette is closed.** A live playing frame is sampled pixel by pixel and
  every colour on it must be one the code declares, so no blend, no
  antialiased edge and no rogue colour can reach the screen unnoticed.
- **Layer order is a contract.** Each layer is drawn inside its own bounds, the
  ground covers the foot of a pipe, and the horizon joins flush — so nothing can
  quietly paint over something it is supposed to sit behind.
- **Determinism is tested, not assumed.** The same seed and the same `dt` give
  the same frame; different seeds and different step counts give different
  frames; and rendering twice never changes the scene. `CloudField` randomises
  once, at construction, and then never consults the rng again.
- **Unseeded randomness cannot be mistaken for determinism.** The unseeded case
  has its own test, which asserts the layout is random *per scene* but fixed for
  the life of that scene.

`671 passed` at the time of writing.

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
│       ├── settings.py          # all tunables (size, FPS, gravity, pipes, colors, audio, difficulty, pixel art)
│       ├── audio.py             # AudioManager: generated effects, volume, mute
│       ├── visuals.py           # Visuals: sky, scenery, clouds, ground, bird sprite, caches
│       ├── pixelfont.py         # PixelFont: the hand-authored 5x7 bitmap font
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
    ├── test_pixelfont.py
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
| Pixel-art scale                         | `PIXEL_SCALE` (= `BIRD_PIXEL_SCALE`)                        |
| Sky                                     | `SKY_BAND_COUNT`, `SKY_TOP_COLOR`, `SKY_BOTTOM_COLOR`       |
| Clouds                                  | `CLOUD_BASE_WIDTH`, `CLOUD_BASE_HEIGHT`, `CLOUD_BLOCK_PER_SCALE`, `CLOUD_SPEED` |
| Distant scenery                         | `DISTANT_HEIGHTS`, `DISTANT_COLORS`, `DISTANT_SPEEDS`        |
| Title screen                            | `TITLE_TEXT_Y`, `TITLE_BIRD_SCALE`, `TITLE_BEST_Y`, `IDLE_BOB_STEP_SECONDS`, `PROMPT_VISIBLE_FRACTION` |
| Panels                                  | `PANEL_*_COLOR`, `PANEL_BORDER_WIDTH`, `PANEL_SHADOW_OFFSET`, `MAX_PANELS` |
| Ground                                  | `GROUND_COLOR`, `GROUND_SOIL_COLOR`, `GROUND_GRASS_HEIGHT`, `GROUND_BLADE_COLUMNS` |
| Audio                                   | `MASTER_VOLUME`, `AUDIO_FREQUENCY`, per-effect gains and pitch |
| Sprite animation                        | `BIRD_TILT_*`, `BIRD_WING_*`, `BIRD_PIXEL_*`                 |
| World motion                            | `GROUND_SCROLL_SPEED`, `CLOUD_SURPLUS_X`                     |

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
- **`PIXEL_SCALE` is the master pixel size.** `BIRD_PIXEL_SCALE` aliases it, and
  every label scale is a multiple of it, so the whole screen stays on one pixel
  grid. Raising it scales the bird, the UI and the authored artwork together.
- **Cloud and scenery sizes are authored, not scaled.** `CLOUD_BASE_WIDTH` and
  `CLOUD_BASE_HEIGHT` must stay large enough for `CLOUD_PROFILE` and
  `CLOUD_SHADE_HEIGHT`, and the tallest `DISTANT_HEIGHTS` entry must fit between
  `GROUND_TOP` and the top of the screen; both are asserted at import.
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
- `pixelfont.py` owns the letterforms, and nothing else does. It is pure data
  plus a paint loop, so the font can grow without touching the game that uses it.
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
- Swap the authored pixel grid in `visuals.py` for a hand-drawn sprite sheet,
  keeping `BirdSprite`'s cached-surface interface so nothing else has to change.

