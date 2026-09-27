# Flappy Bird

A minimal, modular [Pygame](https://www.pygame.org/) Flappy Bird scaffold.

This is the **initial scaffold**: window, main loop, gravity/jump physics and a
pipe placeholder are in place. Graphics are drawn with plain Pygame shapes — no
external image or audio assets — and pipe spawning, collision and scoring are
intentionally left for later.

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

| Key            | Action            |
| -------------- | ----------------- |
| `Space`/`Up`/`W` | Flap upwards     |
| `R`            | Restart          |
| `Esc`          | Quit             |

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
│       ├── pipe.py              # Pipe: gap geometry, scrolling, draw
│       └── utils.py             # small helpers (clamp, frame delta, layout)
└── tests/
    ├── __init__.py              # adds src/ to sys.path, headless SDL
    └── test_game.py
```

## Design notes

- `main.py` only initialises and runs `Game`; all logic lives in the package.
- Every tunable value is a constant in `settings.py`.
- `Game` exposes `handle_events()`, `update(dt)` and `render()` separately from
  `run()`, so individual stages can be driven in tests.
- `update()` is driven by a delta-time in seconds (clamped via
  `utils.frame_delta`) instead of per-frame constants, so physics stays
  frame-rate independent.
- `Game(headless=True)` forces the dummy SDL drivers for automated runs.

## Next steps

- Spawn pipes on a timer using `utils.random_gap_center`.
- Add collision detection between `Player.rect` and each `Pipe.rects`.
- Increment the score when a pipe is passed (`Pipe.has_behind`).
- Swap the placeholder shapes for real sprites and sound.
