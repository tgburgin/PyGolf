# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Let's Golf!** — a top-down 2D pixel-art golf *career* game. The player creates a golfer and progresses through six tours (Amateur Circuit → Challenger → Development → Continental → World → Grand Tour), trying to win all 4 Majors and reach World No. 1. Between rounds they train stats, buy club sets, and (on pro tours) hire staff and sign sponsors. Full gameplay spec in `README.md`.

## Run / develop

```bash
pip install -r requirements.txt          # pygame-ce only
python main.py                           # play the game

pip install pygame_gui                   # editor has an extra dependency
python editor.py                         # course editor (developer tool)
```

- **Python 3.11+** required (uses `X | None` union syntax).
- Uses **`pygame-ce`** (community edition), not stock `pygame`. If stock `pygame` is installed it must be uninstalled first — the two conflict on import.
- No tests, linter, or build step. Sanity check a change by running `python main.py` and exercising the affected flow.
- `saves/` and `data/settings.json` are created at runtime and are gitignored.
- `Plans/` and `manuals/` are gitignored design docs — they may exist locally and contain historical design notes, but are not authoritative. The code and `README.md` are.

## Architecture

### Entry and main loop

`main.py` boots pygame, initialises the `SoundManager` singleton, constructs a `Game`, and runs a fixed 60 FPS loop that delegates `handle_event` / `update(dt)` / `draw` to `Game`.

### State stack (`src/game.py`)

`Game` owns a stack of states (`src/states/*.py`), one per screen: `MainMenuState`, `CharacterCreationState`, `CareerHubState`, `GolfRoundState`, `HoleTransitionState`, `RoundSummaryState`, `TournamentResultsState`, `TourStandingsState`, `HallOfFameState`.

- `push_state` / `pop_state` — overlay (e.g. pause, confirm dialogs).
- `change_state(state, fade=True)` — screen transition with a ~0.45 s black fade; input is blocked during the fade.

States are plain classes with `handle_event`, `update(dt)`, `draw(screen)`. They navigate by calling `game.change_state(NextState(game))`.

`Game` also holds the two pieces of *session* state that outlive any single screen: `game.player` (the `Player` object) and `game.current_tournament` (the active `Tournament`, if any).

### Career model (`src/career/`)

- `player.py` — `Player` dataclass-ish object: stats (`power`, `accuracy`, `short_game`, `putting`, `mental`, `fitness`, each 50→80), money, tour level, season, club set, hired staff, active sponsor, achievements, world ranking, majors won, career log. Has `to_dict` / `from_dict` for save serialisation.
- `tournament.py` — a single event. Opponents' hole-by-hole scores are **pre-simulated at creation** so the leaderboard is deterministic; `get_live_leaderboard(holes_done, …)` compares the player through N holes vs. every opponent through the same N holes. Majors are 2-round events (Grand Tour only).
- `tour.py`, `majors.py`, `rankings.py`, `opponent.py`, `staff.py`, `sponsorship.py` — season schedule, majors schedule, 200-player world rankings, AI opponent pool, staff hires (perm stat bonuses), sponsor deals.

Promotion logic is driven by `PROMOTION_THRESHOLD` / `EVENTS_PER_SEASON` in `tournament.py`; Tour 4→5 also runs a Q-School, Tour 5→6 also requires a top-50 world rank.

### Course model (`src/course/`, `src/golf/`)

A **three-layer grid** per hole (`src/course/hole.py`):
1. `ground_layer` — opaque base tiles (tuples `(tileset_id, col, row)` or `None`).
2. `detail_layer` — transparent overlay sprites (RGBA).
3. `logic_layer` / `grid` — a `list[str]` of single-char terrain codes that drives gameplay.

Terrain codes (`src/golf/terrain.py`):
`X` Tee · `F` Fairway · `R` Rough · `D` Deep rough · `B` Bunker · `W` Water · `T` Trees (also out-of-bounds) · `G` Green.
Each has `dist_mod` and `acc_mod` in `TERRAIN_PROPS` — do not change those numbers casually; they are the core balance dial for shot outcomes.

**1 tile = 10 yards**, rendered at 16 px/tile by default. The renderer (`src/course/renderer.py`) handles the camera, ball trail, terrain fallback colours, and composites the two visual layers.

Courses are JSON files under `data/courses/<tour>/<name>.json`, produced by the editor and loaded by `src/course/course_loader.py`. The loader supports **v2** (visual + attributes) and **v3** (ground + detail + logic) — v2 is silently migrated on read, so when authoring loader changes both formats must keep working. Tileset PNGs referenced by the JSON live under `assets/tilemaps/`; missing files are tolerated (renderer falls back to procedural terrain colours).

In-code course fixtures (a fallback / sample set) live in `src/data/courses_data.py` and `src/data/courses_library.py`. Tour definitions are in `src/data/tours_data.py`, AI opponent pools in `src/data/opponents_data.py`.

### Shot mechanics (`src/golf/`)

- `shot.py` — `ShotController` is a small state machine: `IDLE → AIMING (click-drag) → EXECUTING`. `MAX_DRAG_PIXELS` sets full-power drag distance; `AIM_CLICK_RADIUS` gates how close to the ball the click must be. Shot shape (Draw/Straight/Fade) adds a lateral curve (`SHAPE_CURVE_FRACTION` of shot distance). Scatter is Gaussian and scales with accuracy.
- `club.py` — club definitions, `STARTER_BAG`, tiered club sets (`CLUB_SETS`, `CLUB_SET_ORDER`); the putter auto-selects on the green.
- `ball.py` — ball flight / animation.
- `terrain.py` — see above.

### Save system (`src/utils/save_system.py`)

One JSON file per player at `saves/<sanitised_name>.json`, containing `{save_format, player, tournament}`. `save_format` is currently `1`; bump it and add a migration here if the schema changes. The game auto-saves after every round — any change that touches `Player` or `Tournament` fields must go through their `to_dict`/`from_dict`.

### Audio (`src/utils/sound_manager.py`)

`SoundManager` is a singleton initialised once in `main.py` before the first frame. All sounds are **synthesised at startup** (no assets required to run). If files exist in `assets/sounds/` with the exact names listed in `README.md` they override the synthetic versions. Master / SFX / Ambient volumes are persisted in `data/settings.json`.

### Editor (`tools/editor/`, `editor.py`)

Separate pygame_gui-based tile editor (`EditorApp` in `tools/editor/editor_app.py`). Paints the ground + detail visual layers and an attribute layer that maps to the logic codes. Exports JSON in the v3 format consumed by `course_loader.load_course`. The editor is a dev tool — it is not shipped to players, and breakage there does not break the game (only course authoring).

## Conventions worth knowing

- Module docstrings are the primary documentation — most `.py` files open with a block explaining their purpose, format, or state machine. When adding a new module, follow that style.
- `Player` and `Tournament` have hand-written `to_dict`/`from_dict`; keep those in sync when adding persistent fields.
- Screen size is hard-coded to **1280×720** in `main.py` and referenced by constants in several state files — changing resolution means sweeping those constants.
- Tile source size is hard-coded to **16 px** (`_SOURCE_TILE` in `course_loader.py`; matching constant in `tools/editor/canvas.py`). Those two must stay equal.
- Placeholder colour palettes (`C_BG`, `C_PANEL`, `C_TITLE`, …) are redefined per-state rather than shared — this is intentional so individual screens can be restyled without touching others.
